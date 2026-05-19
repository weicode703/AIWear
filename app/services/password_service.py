import bcrypt


class PasswordService:
    """负责密码哈希和校验。"""

    def hash_password(self, password: str) -> str:
        """把明文密码加密后再存库。"""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """校验明文密码和数据库里的哈希值是否一致。"""
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
