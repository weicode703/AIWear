from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings
from app.models.user import User


class JwtService:
    """负责生成和解析 JWT token。"""

    algorithm = "HS256"

    def generate_token(self, user: User) -> str:
        """给当前用户生成登录 token。"""
        expire_at = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)

        payload = {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "exp": expire_at,
        }

        return jwt.encode(payload, settings.jwt_secret, algorithm=self.algorithm)

    def decode_token(self, token: str) -> dict[str, Any]:
        """解析 token，解析失败时交给调用方处理异常。"""
        return jwt.decode(token, settings.jwt_secret, algorithms=[self.algorithm])

    def get_token_ttl_seconds(self, token: str) -> int:
        """计算 token 距离过期还剩多少秒。"""
        payload = self.decode_token(token)
        exp = payload.get("exp")

        if exp is None:
            return settings.jwt_expire_hours * 3600

        expire_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        ttl = int((expire_at - datetime.now(timezone.utc)).total_seconds())
        return max(ttl, 1)
