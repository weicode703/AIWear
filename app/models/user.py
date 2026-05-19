from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class User(Base):
    """用户表，对齐 Java 版 users。"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=True)


class VerificationCode(Base):
    """验证码表。

    原 Java 版把验证码放在 Redis。
    这里先放数据库，方便你本地先完整跑通。
    """

    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False)
    code = Column(String(6), nullable=False)
    expire_at = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
