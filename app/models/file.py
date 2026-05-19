from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.core.database import Base
from app.models.user import User  # noqa: F401 确保 users 表先注册到 SQLAlchemy 元数据中


class FileRecord(Base):
    """用户文件表，用来保存上传到本地或 OSS 的图片记录。"""

    __tablename__ = "file_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False, default="image")
    storage_backend = Column(String(20), nullable=False, default="local")
    storage_key = Column(String(500), nullable=False)
    file_url = Column(String(1000), nullable=False)
    content_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class ImageOperationRecord(Base):
    """图片编辑/合并历史记录表。"""

    __tablename__ = "image_operation_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(20), nullable=False)
    input_oss_url1 = Column(String(1000), nullable=True)
    input_oss_url2 = Column(String(1000), nullable=True)
    instruction = Column(String(1000), nullable=True)
    output_oss_url = Column(String(1000), nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
