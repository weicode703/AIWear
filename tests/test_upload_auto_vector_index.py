import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.file import FileRecord
from app.services.file_storage_service import FileStorageService
from app.models.user import User
from app.services.image_vector_service import ImageVectorIndexService
from app.services.jwt_service import JwtService


class UploadAutoVectorIndexTest(unittest.TestCase):
    """验证上传图片后会自动尝试写入图片向量索引。"""

    def setUp(self) -> None:
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        self.db = SessionLocal()
        self.created_file_paths: list[Path] = []

        username = f"upload_vec_{uuid.uuid4().hex[:16]}"
        self.user = User(username=username, email=f"{username}@example.com")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.token = JwtService().generate_token(self.user)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.index_calls: list[tuple[str, int]] = []
        self.original_index_image = ImageVectorIndexService.index_image
        self.original_upload_bytes_to_oss = FileStorageService.upload_bytes_to_oss
        FileStorageService.upload_bytes_to_oss = lambda _self, _key, _data, _content_type: None

    def tearDown(self) -> None:
        ImageVectorIndexService.index_image = self.original_index_image
        FileStorageService.upload_bytes_to_oss = self.original_upload_bytes_to_oss

        records = self.db.query(FileRecord).filter(FileRecord.user_id == self.user.id).all()
        for record in records:
            file_path = settings.upload_dir / record.storage_key
            if file_path.exists():
                file_path.unlink()

        self.db.query(FileRecord).filter(FileRecord.user_id == self.user.id).delete()
        self.db.delete(self.user)
        self.db.commit()
        self.db.close()

    def test_upload_image_auto_indexes_vector(self) -> None:
        def fake_index_image(_self, oss_url: str, user_id: int):
            self.index_calls.append((oss_url, user_id))
            return None

        ImageVectorIndexService.index_image = fake_index_image

        response = self.client.post(
            "/api/file/upload/image",
            files={"file": ("test.png", b"fake-image-bytes", "image/png")},
            headers=self.headers,
        )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(200, body["code"])
        self.assertEqual(settings.storage_backend, body["data"]["storageBackend"])
        self.assertTrue(body["data"]["vectorIndexed"])
        self.assertIsNone(body["data"]["vectorIndexError"])
        self.assertEqual(1, len(self.index_calls))
        self.assertEqual(self.user.id, self.index_calls[0][1])
        self.assertEqual(body["data"]["ossUrl"], self.index_calls[0][0])

    def test_upload_image_still_succeeds_when_vector_index_fails(self) -> None:
        def fake_index_image(_self, oss_url: str, user_id: int):
            raise RuntimeError("模型暂时不可用")

        ImageVectorIndexService.index_image = fake_index_image

        response = self.client.post(
            "/api/file/upload/image",
            files={"file": ("test.png", b"fake-image-bytes", "image/png")},
            headers=self.headers,
        )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(200, body["code"])
        self.assertEqual(settings.storage_backend, body["data"]["storageBackend"])
        self.assertFalse(body["data"]["vectorIndexed"])
        self.assertEqual("模型暂时不可用", body["data"]["vectorIndexError"])


if __name__ == "__main__":
    unittest.main()
