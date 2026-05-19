import unittest
import uuid
from pathlib import Path

from sqlalchemy import func

from app.core.database import Base, SessionLocal, engine
from app.models.user import User


class RagServiceTest(unittest.TestCase):
    """验证 RAG 知识库自动导入、检索和聊天回答的最小闭环。"""

    def setUp(self) -> None:
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

        username = f"rag_user_{uuid.uuid4().hex}"
        self.user = User(username=username, email=f"{username}@example.com")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self) -> None:
        from app.models.rag import RagChunk, RagConversation, RagDocument, RagMessage

        self.db.query(RagMessage).delete()
        self.db.query(RagConversation).delete()
        self.db.query(RagChunk).delete()
        self.db.query(RagDocument).delete()
        self.db.delete(self.user)
        self.db.commit()
        self.db.close()

    def test_ensure_knowledge_imported_splits_markdown_into_chunks(self) -> None:
        from app.models.rag import RagChunk, RagDocument
        from app.services.rag_service import RagService

        service = RagService(
            knowledge_path=Path("data/rag/fashion_knowledge.md"),
            embedding_service=FakeEmbeddingService(),
            llm_service=FakeRagLLMService(),
        )

        result = service.ensure_knowledge_imported(self.db)

        self.assertGreaterEqual(result["chunkCount"], 40)
        self.assertEqual(1, self.db.query(RagDocument).count())
        self.assertEqual(result["chunkCount"], self.db.query(RagChunk).count())
        self.assertIsNotNone(self.db.query(func.min(RagChunk.embedding_json)).scalar())

    def test_search_returns_most_related_chunks(self) -> None:
        from app.services.rag_service import RagService

        service = RagService(
            knowledge_path=Path("data/rag/fashion_knowledge.md"),
            embedding_service=FakeEmbeddingService(),
            llm_service=FakeRagLLMService(),
        )
        service.ensure_knowledge_imported(self.db)

        result = service.search(self.db, "苹果型男生日常怎么穿显瘦", top_k=3)

        self.assertEqual("苹果型男生日常怎么穿显瘦", result["query"])
        self.assertEqual(3, len(result["results"]))
        self.assertIn("苹果", result["results"][0]["content"])
        self.assertGreaterEqual(result["results"][0]["score"], result["results"][1]["score"])

    def test_chat_uses_retrieved_knowledge_as_references(self) -> None:
        from app.services.rag_service import RagService

        llm_service = FakeRagLLMService()
        service = RagService(
            knowledge_path=Path("data/rag/fashion_knowledge.md"),
            embedding_service=FakeEmbeddingService(),
            llm_service=llm_service,
        )
        service.ensure_knowledge_imported(self.db)

        result = service.chat(self.db, "苹果型男生日常怎么穿显瘦", top_k=3)

        self.assertIn("苹果型男生日常怎么穿显瘦", result["answer"])
        self.assertEqual(3, len(result["references"]))
        self.assertIn("苹果", llm_service.last_context)

    def test_chat_creates_conversation_and_saves_messages(self) -> None:
        from app.models.rag import RagConversation, RagMessage
        from app.services.rag_service import RagService

        service = RagService(
            knowledge_path=Path("data/rag/fashion_knowledge.md"),
            embedding_service=FakeEmbeddingService(),
            llm_service=FakeRagLLMService(),
        )
        service.ensure_knowledge_imported(self.db)

        result = service.chat(
            self.db,
            "男生苹果型身材怎么穿",
            user_id=self.user.id,
            conversation_id=None,
            top_k=3,
        )

        self.assertIsInstance(result["conversationId"], int)
        self.assertEqual(1, self.db.query(RagConversation).count())
        self.assertEqual(2, self.db.query(RagMessage).count())

        messages = service.list_messages(self.db, self.user.id, result["conversationId"])
        self.assertEqual(["user", "assistant"], [item["role"] for item in messages])

    def test_chat_stream_yields_chunks_and_saves_messages(self) -> None:
        from app.models.rag import RagMessage
        from app.services.rag_service import RagService

        service = RagService(
            knowledge_path=Path("data/rag/fashion_knowledge.md"),
            embedding_service=FakeEmbeddingService(),
            llm_service=FakeRagLLMService(),
        )
        service.ensure_knowledge_imported(self.db)

        events = list(
            service.chat_stream(
                self.db,
                "stream test",
                user_id=self.user.id,
                conversation_id=None,
                top_k=3,
            )
        )

        self.assertEqual("start", events[0]["type"])
        self.assertIn("progress", [item["type"] for item in events])
        self.assertEqual(["delta", "delta"], [item["type"] for item in events if item["type"] == "delta"])
        self.assertEqual("done", events[-1]["type"])
        self.assertEqual("fake", events[-1]["modelSource"])
        self.assertEqual(2, self.db.query(RagMessage).count())

        saved_answer = (
            self.db.query(RagMessage)
            .filter(RagMessage.role == "assistant")
            .first()
            .content
        )
        self.assertEqual("stream answer", saved_answer)

    def test_chat_uses_recent_messages_and_trims_old_context(self) -> None:
        from app.models.rag import RagConversation, RagMessage
        from app.services.rag_service import RagService

        llm_service = FakeRagLLMService()
        service = RagService(
            knowledge_path=Path("data/rag/fashion_knowledge.md"),
            embedding_service=FakeEmbeddingService(),
            llm_service=llm_service,
            memory_message_limit=4,
        )
        service.ensure_knowledge_imported(self.db)

        conversation = RagConversation(user_id=self.user.id, title="测试会话")
        self.db.add(conversation)
        self.db.flush()
        for index in range(6):
            self.db.add(
                RagMessage(
                    conversation_id=conversation.id,
                    role="user" if index % 2 == 0 else "assistant",
                    content=f"旧消息{index}",
                )
            )
        self.db.commit()

        service.chat(
            self.db,
            "继续推荐",
            user_id=self.user.id,
            conversation_id=conversation.id,
            top_k=3,
        )

        self.assertNotIn("旧消息0", llm_service.last_history)
        self.assertNotIn("旧消息1", llm_service.last_history)
        self.assertIn("旧消息2", llm_service.last_history)
        self.assertIn("旧消息5", llm_service.last_history)

    def test_delete_conversation_removes_messages(self) -> None:
        from app.services.rag_service import RagService

        service = RagService(
            knowledge_path=Path("data/rag/fashion_knowledge.md"),
            embedding_service=FakeEmbeddingService(),
            llm_service=FakeRagLLMService(),
        )
        service.ensure_knowledge_imported(self.db)
        result = service.chat(
            self.db,
            "男生日常怎么穿",
            user_id=self.user.id,
            conversation_id=None,
            top_k=3,
        )

        service.delete_conversation(self.db, self.user.id, result["conversationId"])

        self.assertEqual([], service.list_conversations(self.db, self.user.id))
        self.assertEqual([], service.list_messages(self.db, self.user.id, result["conversationId"]))


class FakeEmbeddingService:
    """测试用假向量服务：用关键词控制相似度，避免加载真实 CLIP 模型。"""

    def encode_text(self, text: str) -> list[float]:
        return [
            1.0 if "苹果" in text or "O型" in text else 0.0,
            1.0 if "男" in text else 0.0,
            1.0 if "显瘦" in text else 0.0,
        ]


class FakeRagLLMService:
    """测试用假 LLM：记录上下文，并返回稳定回答。"""

    def __init__(self) -> None:
        self.last_context = ""
        self.last_history = ""

    def generate_chat_answer(self, message: str, context: str, history: str = "") -> tuple[str, str]:
        self.last_context = context
        self.last_history = history
        return f"根据知识库，{message} 可以选择挺括上衣和直筒裤。", "fake"

    def stream_chat_answer(self, message: str, context: str, history: str = ""):
        self.last_context = context
        self.last_history = history
        yield "stream ", "fake"
        yield "answer", "fake"


if __name__ == "__main__":
    unittest.main()
