import uuid
import unittest

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.file import FileRecord, ImageOperationRecord
from app.models.user import User
from app.services.image_operation_service import ImageGenerationService
from app.services.jwt_service import JwtService


class FileOperationApiTest(unittest.TestCase):
    """验证图片编辑、合并和历史记录接口的最小闭环。"""

    def setUp(self) -> None:
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        self.db = SessionLocal()

        username = f"test_user_{uuid.uuid4().hex}"
        self.user = User(username=username, email=None)
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.token = JwtService().generate_token(self.user)
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.image1 = self._create_file_record("image1.png", "/uploads/images/test/image1.png")
        self.image2 = self._create_file_record("image2.png", "/uploads/images/test/image2.png")

        self.original_edit = ImageGenerationService.edit_image
        self.original_merge = ImageGenerationService.merge_images
        ImageGenerationService.edit_image = lambda _self, _image, _instruction: "/uploads/results/edit.png"
        ImageGenerationService.merge_images = (
            lambda _self, _image1, _image2, _instruction: "/uploads/results/merge.png"
        )

    def tearDown(self) -> None:
        ImageGenerationService.edit_image = self.original_edit
        ImageGenerationService.merge_images = self.original_merge

        self.db.query(ImageOperationRecord).filter(ImageOperationRecord.user_id == self.user.id).delete()
        self.db.query(FileRecord).filter(FileRecord.user_id == self.user.id).delete()
        self.db.delete(self.user)
        self.db.commit()
        self.db.close()

    def _create_file_record(self, file_name: str, file_url: str) -> FileRecord:
        record = FileRecord(
            user_id=self.user.id,
            file_name=file_name,
            file_type="image",
            storage_backend="local",
            storage_key=file_url.removeprefix("/uploads/"),
            file_url=file_url,
            content_type="image/png",
            file_size=10,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def test_edit_merge_and_history_use_current_user(self) -> None:
        edit_resp = self.client.post(
            "/api/file/edit",
            json={"image": self.image1.file_url, "instruction": "加一个黑色眼镜"},
            headers=self.headers,
        )
        self.assertEqual(200, edit_resp.status_code)
        self.assertEqual(200, edit_resp.json()["code"])
        self.assertEqual("/uploads/results/edit.png", edit_resp.json()["data"]["url"])

        merge_resp = self.client.post(
            "/api/file/merge",
            json={
                "image1": self.image1.file_url,
                "image2": self.image2.file_url,
                "instruction": "把衣服合到人物身上",
            },
            headers=self.headers,
        )
        self.assertEqual(200, merge_resp.status_code)
        self.assertEqual(200, merge_resp.json()["code"])
        self.assertEqual("/uploads/results/merge.png", merge_resp.json()["data"]["url"])

        history_resp = self.client.get("/api/record/my", headers=self.headers)
        self.assertEqual(200, history_resp.status_code)
        actions = [item["action"] for item in history_resp.json()["data"]]
        self.assertEqual(["merge", "edit"], actions[:2])


if __name__ == "__main__":
    unittest.main()
