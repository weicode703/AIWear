from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.services.jwt_service import JwtService
from app.services.token_blacklist_service import TokenBlacklistService


bearer_scheme = HTTPBearer(
    scheme_name="HTTPBearer",
    description="只填写登录接口返回的 token 即可，Swagger 会自动加上 Bearer 前缀。",
)


def get_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """从请求头 Authorization: Bearer xxx 中取出 token 字符串。"""
    return credentials.credentials


def get_current_user(
    token: str = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> User:
    """从请求头里的 token 解析当前登录用户。"""
    blacklist_service = TokenBlacklistService()
    if blacklist_service.is_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="当前登录已退出，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jwt_service = JwtService()
    try:
        payload = jwt_service.decode_token(token)
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证无效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证缺少用户信息",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_user_id(current_user: User = Depends(get_current_user)) -> int:
    """只需要 user_id 的接口可以直接复用这个依赖。"""
    return int(current_user.id)
