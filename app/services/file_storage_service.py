import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings


class FileStorageService:
    """文件存储服务。

    当前支持两种模式：
    1. local：保存到本地 uploads 目录，适合本地学习调试；
    2. oss：上传到阿里云 OSS，适合前端展示和云服务器部署。
    """

    allowed_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

    def save_image(self, user_id: int, file: UploadFile) -> tuple[str, str, int]:
        """保存图片文件，返回 storage_key、访问 URL、文件大小。"""
        original_name = file.filename or "image.png"
        suffix = Path(original_name).suffix.lower() or ".png"

        if suffix not in self.allowed_suffixes:
            raise ValueError("只支持上传 png、jpg、jpeg、webp、gif、bmp 格式的图片")

        file_name = f"{uuid.uuid4().hex}{suffix}"
        storage_key = f"images/{user_id}/{file_name}"

        if settings.storage_backend.lower() == "oss":
            return self.save_image_to_oss(file, storage_key)

        return self.save_image_to_local(file, storage_key)

    def save_image_to_local(self, file: UploadFile, storage_key: str) -> tuple[str, str, int]:
        """把图片保存到本地 uploads 目录。"""
        target_path = settings.upload_dir / storage_key
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with target_path.open("wb") as target:
            shutil.copyfileobj(file.file, target)

        file_size = target_path.stat().st_size
        file_url = f"{settings.local_file_base_url}/{storage_key}".replace("\\", "/")
        return storage_key, file_url, file_size

    def save_image_to_oss(self, file: UploadFile, storage_key: str) -> tuple[str, str, int]:
        """把图片上传到阿里云 OSS。"""
        self.validate_oss_config()

        data = file.file.read()
        content_type = file.content_type or "application/octet-stream"
        self.upload_bytes_to_oss(storage_key, data, content_type)

        file_url = f"{settings.oss_base_url.rstrip('/')}/{storage_key}"
        return storage_key, file_url, len(data)

    def validate_oss_config(self) -> None:
        """检查 OSS 必填配置是否齐全。"""
        missing = []
        if not settings.oss_endpoint:
            missing.append("OSS_ENDPOINT")
        if not settings.oss_bucket:
            missing.append("OSS_BUCKET")
        if not settings.oss_access_key_id:
            missing.append("OSS_ACCESS_KEY_ID")
        if not settings.oss_access_key_secret:
            missing.append("OSS_ACCESS_KEY_SECRET")
        if not settings.oss_base_url:
            missing.append("OSS_BASE_URL")

        if missing:
            raise RuntimeError(f"OSS 配置缺失：{', '.join(missing)}")

    def upload_bytes_to_oss(self, storage_key: str, data: bytes, content_type: str) -> None:
        """调用阿里云 OSS SDK 上传图片二进制内容。"""
        try:
            import oss2
        except ImportError as exc:
            raise RuntimeError("缺少 oss2 依赖，请先执行 pip install oss2") from exc

        auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
        bucket = oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket)
        bucket.put_object(
            storage_key,
            data,
            headers={"Content-Type": content_type},
        )
