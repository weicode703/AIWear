from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_token, get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.user import (
    AuthRequest,
    CurrentUserResponse,
    SendVerificationCodeRequest,
)
from app.services.jwt_service import JwtService
from app.services.token_blacklist_service import TokenBlacklistService
from app.services.user_service import UserService

router = APIRouter(prefix="/api/user", tags=["用户模块"])


@router.post("/send-code", response_model=ApiResponse)
def send_verification_code(
    request: SendVerificationCodeRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """发送邮箱验证码接口。"""
    user_service = UserService(db)

    try:
        data = user_service.send_verification_code(request)
        return ApiResponse(code=200, message="验证码发送成功", data=data.model_dump())
    except ValueError as exc:
        return ApiResponse(code=400, message=str(exc), data=None)
    except Exception as exc:
        print(f"发送验证码接口异常：{exc}")
        return ApiResponse(code=500, message="验证码发送失败，请稍后重试", data=None)


@router.post("/auth", response_model=ApiResponse)
def auth(
    request: AuthRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """统一认证接口。"""
    user_service = UserService(db)

    try:
        data = user_service.auth(request)
        return ApiResponse(code=200, message="操作成功", data=data.model_dump())
    except ValueError as exc:
        return ApiResponse(code=400, message=str(exc), data=None)
    except Exception as exc:
        print(f"统一认证接口异常：{exc}")
        return ApiResponse(code=500, message="认证失败，请稍后重试", data=None)


@router.get("/me", response_model=ApiResponse)
def get_me(current_user: User = Depends(get_current_user)) -> ApiResponse:
    """获取当前登录用户信息，需要在请求头中携带 Bearer token。"""
    data = CurrentUserResponse(
        user_id=current_user.id,
        username=current_user.username,
        email=current_user.email,
    )
    return ApiResponse(code=200, message="操作成功", data=data.model_dump())


@router.post("/logout", response_model=ApiResponse)
def logout(
    token: str = Depends(get_current_token),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """退出登录接口，把当前 token 加入 Redis 黑名单。"""
    jwt_service = JwtService()
    blacklist_service = TokenBlacklistService()
    ttl_seconds = jwt_service.get_token_ttl_seconds(token)
    blacklist_service.add_token(token, ttl_seconds)

    return ApiResponse(
        code=200,
        message="退出登录成功",
        data={"user_id": current_user.id},
    )
