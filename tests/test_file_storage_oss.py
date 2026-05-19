import unittest
import uuid
from io import BytesIO
from types import SimpleNamespace

from app.core.config import settings
from app.services.file_storage_service import FileStorageService


class FileStorageOssTest(unittest.TestCase):
    """验证文件存储服务在 OSS 模式下会上传到阿里云 OSS。"""

    def setUp(self) -> None:
        self.original_storage_backend = settings.storage_backend
        self.original_oss_endpoint = settings.oss_endpoint
        self.original_oss_bucket = settings.oss_bucket
        self.original_oss_base_url = settings.oss_base_url
        self.original_access_key_id = settings.oss_access_key_id
        self.original_access_key_secret = settings.oss_access_key_secret
        self.original_upload_method = getattr(FileStorageService, "upload_bytes_to_oss", None)

        settings.storage_backend = "oss"
        settings.oss_endpoint = "https://oss-cn-beijing.aliyuncs.com"
        settings.oss_bucket = "ai--wear"
        settings.oss_base_url = "https://ai--wear.oss-cn-beijing.aliyuncs.com"
        settings.oss_access_key_id = "test-access-key-id"
        settings.oss_access_key_secret = "test-access-key-secret"

        self.uploaded: list[tuple[str, bytes, str]] = []

        def fake_upload(_self, storage_key: str, data: bytes, content_type: str) -> None:
            self.uploaded.append((storage_key, data, content_type))

        FileStorageService.upload_bytes_to_oss = fake_upload

    def tearDown(self) -> None:
        settings.storage_backend = self.original_storage_backend
        settings.oss_endpoint = self.original_oss_endpoint
        settings.oss_bucket = self.original_oss_bucket
        settings.oss_base_url = self.original_oss_base_url
        settings.oss_access_key_id = self.original_access_key_id
        settings.oss_access_key_secret = self.original_access_key_secret

        if self.original_upload_method is None:
            delattr(FileStorageService, "upload_bytes_to_oss")
        else:
            FileStorageService.upload_bytes_to_oss = self.original_upload_method

    def test_save_image_uploads_to_oss_when_backend_is_oss(self) -> None:
        file = SimpleNamespace(
            filename=f"{uuid.uuid4().hex}.png",
            content_type="image/png",
            file=BytesIO(b"fake-image-bytes"),
        )

        storage_key, file_url, file_size = FileStorageService().save_image(user_id=7, file=file)

        self.assertEqual(1, len(self.uploaded))
        self.assertTrue(storage_key.startswith("images/7/"))
        self.assertTrue(storage_key.endswith(".png"))
        self.assertEqual(f"https://ai--wear.oss-cn-beijing.aliyuncs.com/{storage_key}", file_url)
        self.assertEqual(len(b"fake-image-bytes"), file_size)
        self.assertEqual((storage_key, b"fake-image-bytes", "image/png"), self.uploaded[0])


if __name__ == "__main__":
    unittest.main()
