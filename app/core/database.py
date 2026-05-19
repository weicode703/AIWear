from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """所有数据库模型的基类。"""
    pass


# SQLite 需要特殊配置，允许 FastAPI 多线程访问
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# 创建数据库引擎
engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args=connect_args,
)

# 创建 Session 工厂
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """给路由函数提供数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
