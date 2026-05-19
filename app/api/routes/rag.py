import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.rag import RagChatRequest, RagSearchRequest
from app.services.rag_service import RagService


router = APIRouter(prefix="/api/rag", tags=["RAG 穿搭聊天"])
rag_service = RagService()


@router.get("/status")
def rag_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """查看 RAG 知识库是否已经导入。"""
    _ = current_user
    return {
        "code": 200,
        "message": "查询成功",
        "data": rag_service.get_status(db),
    }


@router.post("/search")
def rag_search(
    request: RagSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """调试用：只检索知识片段，不调用大模型。"""
    _ = current_user
    result = rag_service.search(db, request.query, request.topK)
    return {
        "code": 200,
        "message": "检索成功",
        "data": result,
    }


@router.post("/chat")
def rag_chat(
    request: RagChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """用户聊天接口：输入穿搭问题，返回结合知识库的回答。"""
    result = rag_service.chat(
        db,
        request.message,
        user_id=current_user.id,
        conversation_id=request.conversationId,
        top_k=request.topK,
    )
    return {
        "code": 200,
        "message": "回答成功",
        "data": result,
    }


@router.post("/chat/stream")
def rag_chat_stream(
    request: RagChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """RAG 流式聊天接口：使用 SSE 持续返回生成中的回答片段。"""

    def event_generator():
        for event in rag_service.chat_stream(
            db,
            request.message,
            user_id=current_user.id,
            conversation_id=request.conversationId,
            top_k=request.topK,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            # 关闭代理缓存，避免前端等到一大段内容后才看到输出。
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations")
def list_rag_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """查询当前用户的 RAG 会话列表。"""
    return {
        "code": 200,
        "message": "查询成功",
        "data": rag_service.list_conversations(db, current_user.id),
    }


@router.get("/conversations/{conversation_id}/messages")
def list_rag_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """查询某个 RAG 会话的消息列表。"""
    return {
        "code": 200,
        "message": "查询成功",
        "data": rag_service.list_messages(db, current_user.id, conversation_id),
    }


@router.delete("/conversations/{conversation_id}")
def delete_rag_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """删除某个 RAG 会话。"""
    rag_service.delete_conversation(db, current_user.id, conversation_id)
    return {
        "code": 200,
        "message": "删除成功",
        "data": None,
    }
