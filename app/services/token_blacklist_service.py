import hashlib

from redis import Redis

from app.core.config import settings


class TokenBlacklistService:
    """负责管理已经退出登录的 token。"""

    def __init__(self) -> None:
        self.redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        self.key_prefix = "auth:blacklist:"

    def build_key(self, token: str) -> str:
        """用 token 摘要生成 Redis key，避免把完整 token 暴露在 Redis key 里。"""
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return f"{self.key_prefix}{token_hash}"

    def add_token(self, token: str, ttl_seconds: int) -> None:
        """把 token 加入黑名单，直到它自然过期。"""
        key = self.build_key(token)
        self.redis_client.set(key, "1", ex=max(ttl_seconds, 1))

    def is_blacklisted(self, token: str) -> bool:
        """判断 token 是否已经退出登录。"""
        key = self.build_key(token)
        return bool(self.redis_client.exists(key))
