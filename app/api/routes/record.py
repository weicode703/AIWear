from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.file_service import FileService


router = APIRouter(prefix="/api/record", tags=["历史记录"])


@router.get("/my", response_model=ApiResponse)
def my_records(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """查询当前用户的图片编辑/合并历史记录。"""
    data = FileService(db).list_my_records(current_user.id)
    return ApiResponse(
        code=200,
        message="操作成功",
        data=[item.model_dump() for item in data],
    )
