import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.rag import RagChunk, RagConversation, RagDocument, RagMessage
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService


class RagService:
    """RAG 服务：负责知识导入、知识检索和聊天回答。"""

    def __init__(
        self,
        knowledge_path: Path | None = None,
        embedding_service: EmbeddingService | None = None,
        llm_service: LLMService | None = None,
        memory_message_limit: int = 8,
    ) -> None:
        self.knowledge_path = knowledge_path or Path("data/rag/fashion_knowledge.md")
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_service = llm_service or LLMService()
        self.memory_message_limit = memory_message_limit

    def ensure_knowledge_imported(self, db: Session) -> dict:
        """确保系统穿搭知识库已经导入数据库。

        如果同名文档已经导入过，就直接返回当前状态，避免每次启动重复写入。
        """
        source_name = self.knowledge_path.name
        existing = db.query(RagDocument).filter(RagDocument.source_name == source_name).first()
        if existing:
            return {
                "imported": True,
                "documentCount": db.query(RagDocument).count(),
                "chunkCount": db.query(RagChunk).count(),
                "source": source_name,
            }

        if not self.knowledge_path.exists():
            raise FileNotFoundError(f"RAG 知识库文档不存在：{self.knowledge_path}")

        content = self.knowledge_path.read_text(encoding="utf-8")
        chunks = self.split_markdown_knowledge(content)
        document = RagDocument(source_name=source_name, chunk_count=len(chunks))
        db.add(document)
        db.flush()

        for index, chunk in enumerate(chunks):
            embedding = self.embedding_service.encode_text(chunk["text"])
            db.add(
                RagChunk(
                    document_id=document.id,
                    chunk_index=index,
                    title=chunk["title"],
                    content=chunk["text"],
                    embedding_json=json.dumps(embedding),
                )
            )

        db.commit()
        return {
            "imported": True,
            "documentCount": db.query(RagDocument).count(),
            "chunkCount": db.query(RagChunk).count(),
            "source": source_name,
        }

    def get_status(self, db: Session) -> dict:
        """返回 RAG 知识库当前状态，方便前端和 /docs 调试。"""
        source_name = self.knowledge_path.name
        return {
            "imported": db.query(RagChunk).count() > 0,
            "documentCount": db.query(RagDocument).count(),
            "chunkCount": db.query(RagChunk).count(),
            "source": source_name,
        }

    def search(self, db: Session, query: str, top_k: int = 5) -> dict:
        """检索和用户问题最相关的知识片段。"""
        self.ensure_knowledge_imported(db)
        query_vector = self.embedding_service.encode_text(query)

        scored_items = []
        chunks = db.query(RagChunk).order_by(RagChunk.id.asc()).all()
        source_name = self.knowledge_path.name
        for chunk in chunks:
            chunk_vector = json.loads(chunk.embedding_json)
            score = self.cosine_similarity(query_vector, chunk_vector)
            scored_items.append(
                {
                    "title": chunk.title,
                    "content": chunk.content,
                    "score": round(score, 6),
                    "chunkIndex": chunk.chunk_index,
                    "source": source_name,
                }
            )

        scored_items.sort(key=lambda item: item["score"], reverse=True)
        return {"query": query, "results": scored_items[:top_k]}

    def chat(
        self,
        db: Session,
        message: str,
        user_id: int | None = None,
        conversation_id: int | None = None,
        top_k: int = 5,
    ) -> dict:
        """RAG 聊天：保存用户消息，结合记忆和知识库生成回答。"""
        conversation = None
        history_text = ""
        if user_id is not None:
            conversation = self.get_or_create_conversation(db, user_id, conversation_id, message)
            history_messages = self.get_recent_memory_messages(db, conversation.id)
            history_text = self.build_history_text(history_messages)
            self.add_message(db, conversation.id, "user", message, commit=False)

        search_result = self.search(db, message, top_k)
        references = search_result["results"]
        context = self.build_context(references)
        answer, model_source = self.llm_service.generate_chat_answer(message, context, history_text)

        if conversation is not None:
            self.add_message(db, conversation.id, "assistant", answer, commit=False)
            conversation.updated_at = datetime.now(timezone.utc)
            db.commit()

        return {
            "conversationId": conversation.id if conversation is not None else 0,
            "answer": answer,
            "modelSource": model_source,
            "references": references,
        }

    def chat_stream(
        self,
        db: Session,
        message: str,
        user_id: int,
        conversation_id: int | None = None,
        top_k: int = 5,
    ):
        """RAG 流式聊天：边生成边产出文本块，结束后保存完整助手消息。"""
        conversation = self.get_or_create_conversation(db, user_id, conversation_id, message)
        history_messages = self.get_recent_memory_messages(db, conversation.id)
        history_text = self.build_history_text(history_messages)
        self.add_message(db, conversation.id, "user", message, commit=False)

        # 先把会话 ID 发给前端，让页面立刻进入“思考中”，不要等检索完成才有反应。
        yield {
            "type": "start",
            "conversationId": conversation.id,
            "references": [],
        }

        answer_parts: list[str] = []
        model_source = "fallback"
        try:
            yield {
                "type": "progress",
                "message": "正在检索穿搭知识",
            }
            search_result = self.search(db, message, top_k)
            references = search_result["results"]
            context = self.build_context(references)

            yield {
                "type": "progress",
                "message": "正在组织回答",
                "references": references,
            }
            for chunk, source in self.llm_service.stream_chat_answer(message, context, history_text):
                model_source = source
                answer_parts.append(chunk)
                yield {
                    "type": "delta",
                    "text": chunk,
                }

            answer = "".join(answer_parts).strip()
            if not answer:
                answer = "暂时没有生成有效回答，请换一种问法再试。"

            self.add_message(db, conversation.id, "assistant", answer, commit=False)
            conversation.updated_at = datetime.now(timezone.utc)
            db.commit()
            yield {
                "type": "done",
                "conversationId": conversation.id,
                "modelSource": model_source,
            }
        except Exception as exc:
            db.rollback()
            yield {
                "type": "error",
                "message": f"生成回答失败：{exc}",
            }

    def list_conversations(self, db: Session, user_id: int) -> list[dict]:
        """查询当前用户的 RAG 会话列表。"""
        rows = (
            db.query(RagConversation)
            .filter(RagConversation.user_id == user_id)
            .order_by(RagConversation.updated_at.desc(), RagConversation.id.desc())
            .all()
        )
        return [
            {
                "id": row.id,
                "title": row.title,
                "updatedAt": row.updated_at.isoformat(),
            }
            for row in rows
        ]

    def list_messages(self, db: Session, user_id: int, conversation_id: int) -> list[dict]:
        """查询某个会话下的消息。"""
        conversation = self.get_user_conversation(db, user_id, conversation_id)
        if conversation is None:
            return []

        rows = (
            db.query(RagMessage)
            .filter(RagMessage.conversation_id == conversation.id)
            .order_by(RagMessage.id.asc())
            .all()
        )
        return [
            {
                "id": row.id,
                "role": row.role,
                "content": row.content,
                "createdAt": row.created_at.isoformat(),
            }
            for row in rows
        ]

    def delete_conversation(self, db: Session, user_id: int, conversation_id: int) -> None:
        """删除当前用户的某个会话和对应消息。"""
        conversation = self.get_user_conversation(db, user_id, conversation_id)
        if conversation is None:
            return
        db.query(RagMessage).filter(RagMessage.conversation_id == conversation.id).delete()
        db.delete(conversation)
        db.commit()

    def get_or_create_conversation(
        self,
        db: Session,
        user_id: int,
        conversation_id: int | None,
        first_message: str,
    ) -> RagConversation:
        """取已有会话；没有传会话 ID 时自动创建新会话。"""
        if conversation_id:
            conversation = self.get_user_conversation(db, user_id, conversation_id)
            if conversation is not None:
                return conversation

        title = self.build_conversation_title(first_message)
        conversation = RagConversation(user_id=user_id, title=title)
        db.add(conversation)
        db.flush()
        return conversation

    def get_user_conversation(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
    ) -> RagConversation | None:
        """只允许访问自己的会话。"""
        return (
            db.query(RagConversation)
            .filter(RagConversation.id == conversation_id, RagConversation.user_id == user_id)
            .first()
        )

    def add_message(
        self,
        db: Session,
        conversation_id: int,
        role: str,
        content: str,
        commit: bool = True,
    ) -> RagMessage:
        """新增一条会话消息。"""
        message = RagMessage(conversation_id=conversation_id, role=role, content=content)
        db.add(message)
        if commit:
            db.commit()
            db.refresh(message)
        return message

    def get_recent_memory_messages(self, db: Session, conversation_id: int) -> list[RagMessage]:
        """只取最近几条消息作为短期记忆，避免上下文过长。"""
        rows = (
            db.query(RagMessage)
            .filter(RagMessage.conversation_id == conversation_id)
            .order_by(RagMessage.id.desc())
            .limit(self.memory_message_limit)
            .all()
        )
        return list(reversed(rows))

    def build_history_text(self, messages: list[RagMessage]) -> str:
        """把最近消息整理成模型可读的短期记忆。"""
        labels = {"user": "用户", "assistant": "AI"}
        return "\n".join(f"{labels.get(item.role, item.role)}：{item.content}" for item in messages)

    def build_conversation_title(self, message: str) -> str:
        """用首条问题生成会话标题，避免前端出现一堆无意义的新会话。"""
        clean = re.sub(r"\s+", " ", message).strip()
        return clean[:18] or "新的穿搭问答"

    def split_markdown_knowledge(self, content: str) -> list[dict[str, str]]:
        """按三级标题切分知识点。

        你的知识库每条知识都以 `### 1.1 xxx` 这种标题开头，所以按它切块最稳定。
        """
        pattern = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
        matches = list(pattern.finditer(content))
        chunks: list[dict[str, str]] = []

        for index, match in enumerate(matches):
            title = match.group(1).strip()
            if not re.match(r"^\d+\.\d+\s+", title):
                continue
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            text = content[start:end].strip()
            if text:
                chunks.append({"title": title, "text": text})

        return chunks

    def build_context(self, references: list[dict]) -> str:
        """把命中的知识片段整理成给 LLM 阅读的上下文。"""
        parts = []
        for item in references:
            parts.append(f"【{item['title']}】\n{item['content']}")
        return "\n\n".join(parts)

    def cosine_similarity(self, left: list[float], right: list[float]) -> float:
        """计算两个向量的余弦相似度。"""
        if not left or not right or len(left) != len(right):
            return 0.0

        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)
