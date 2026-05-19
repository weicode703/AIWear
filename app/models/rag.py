from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.core.database import Base


class RagDocument(Base):
    """RAG 知识源文档表。

    这里保存的是系统知识库文档信息，不是普通用户上传的聊天内容。
    """

    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(255), unique=True, nullable=False)
    chunk_count = Column(Integer, default=0, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RagChunk(Base):
    """RAG 知识片段表。

    第一版为了兼容 SQLite 和 PostgreSQL，先用 JSON 字符串保存向量。
    后面切到 PostgreSQL + pgvector 时，可以把 embedding_json 换成 vector 字段。
    """

    __tablename__ = "rag_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("rag_documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RagConversation(Base):
    """RAG 会话表。

    一个用户可以有多个穿搭问答会话，每个会话保存自己的短期记忆。
    """

    __tablename__ = "rag_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RagMessage(Base):
    """RAG 会话消息表。"""

    __tablename__ = "rag_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("rag_conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
