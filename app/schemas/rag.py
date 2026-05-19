from pydantic import BaseModel, Field


class RagChatRequest(BaseModel):
    """RAG 聊天请求。"""

    message: str = Field(..., min_length=1, description="用户输入的穿搭问题")
    conversationId: int | None = Field(default=None, description="会话 ID；为空时自动创建新会话")
    topK: int = Field(default=5, ge=1, le=10, description="检索多少条相关知识")


class RagSearchRequest(BaseModel):
    """RAG 知识检索请求，主要用于开发调试。"""

    query: str = Field(..., min_length=1, description="要检索的穿搭问题")
    topK: int = Field(default=5, ge=1, le=10, description="返回多少条知识片段")


class RagReferenceItem(BaseModel):
    """RAG 命中的知识片段。"""

    title: str
    content: str
    score: float
    chunkIndex: int
    source: str


class RagChatResponse(BaseModel):
    """RAG 聊天响应。"""

    conversationId: int
    answer: str
    modelSource: str
    references: list[RagReferenceItem]


class RagConversationItem(BaseModel):
    """RAG 会话列表项。"""

    id: int
    title: str
    updatedAt: str


class RagMessageItem(BaseModel):
    """RAG 单条聊天消息。"""

    id: int
    role: str
    content: str
    createdAt: str


class RagSearchResponse(BaseModel):
    """RAG 检索响应。"""

    query: str
    results: list[RagReferenceItem]


class RagStatusResponse(BaseModel):
    """RAG 知识库状态。"""

    imported: bool
    documentCount: int
    chunkCount: int
    source: str
