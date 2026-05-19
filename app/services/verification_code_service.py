import random

from redis import Redis

from app.core.config import settings


class VerificationCodeService:
    """负责验证码相关逻辑。

    这一版把验证码放到 Redis 里，利用 Redis 的自动过期能力
    来管理验证码有效期。
    """

    def __init__(self) -> None:
        self.redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        self.key_prefix = "verification:code:"

    def build_key(self, email: str) -> str:
        """根据邮箱生成 Redis key。"""
        return f"{self.key_prefix}{email}"

    def generate_code(self) -> str:
        """生成 6 位数字验证码。"""
        return str(random.randint(100000, 999999))

    def has_valid_code(self, email: str) -> bool:
        """检查当前邮箱是否还有未过期验证码。"""
        key = self.build_key(email)
        return bool(self.redis_client.exists(key))

    def save_code(self, email: str, code: str) -> None:
        """保存验证码，并设置自动过期时间。"""
        key = self.build_key(email)
        self.redis_client.set(
            key,
            code,
            ex=settings.verification_code_expire_seconds,
        )

    def delete_code(self, email: str) -> None:
        """删除当前邮箱对应的验证码。

        主要用于发邮件失败时，避免 Redis 里留下无效验证码。
        """
        key = self.build_key(email)
        self.redis_client.delete(key)

    def verify_code(self, email: str, code: str) -> bool:
        """校验验证码。

        成功后删除验证码，防止重复使用。
        """
        key = self.build_key(email)
        saved_code = self.redis_client.get(key)

        if saved_code is None:
            return False

        if saved_code != code:
            return False

        self.redis_client.delete(key)
        return True
