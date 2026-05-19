import json
import unittest
import uuid

from fastapi.testclient import TestClient
from redis import Redis

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.user import User
from app.services.image_vector_service import ImageVectorIndexService
from app.services.jwt_service import JwtService


class ImageVectorSearchApiTest(unittest.TestCase):
    """验证文搜图和图搜图会在当前用户的 Redis 图片向量里查找结果。"""

    def setUp(self) -> None:
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        self.db = SessionLocal()
        self.redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        self.vector_service = ImageVectorIndexService()

        username = f"search_user_{uuid.uuid4().hex}"
        self.user = User(username=username, email=f"{username}@example.com")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.token = JwtService().generate_token(self.user)
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.redis_keys: list[str] = []

        self.white_url = f"https://oss.example.com/{uuid.uuid4().hex}-white.png"
        self.black_url = f"https://oss.example.com/{uuid.uuid4().hex}-black.png"
        self._save_vector(self.white_url, "白色衬衫，休闲风格", [1.0, 0.0, 0.0])
        self._save_vector(self.black_url, "黑色外套，通勤风格", [0.0, 1.0, 0.0])

        self.original_encode_text = ImageVectorIndexService.encode_text
        self.original_encode_image = ImageVectorIndexService.encode_image
        ImageVectorIndexService.encode_text = lambda _self, _text: [1.0, 0.0, 0.0]
        ImageVectorIndexService.encode_image = lambda _self, _image_data: [0.0, 1.0, 0.0]

    def tearDown(self) -> None:
        ImageVectorIndexService.encode_text = self.original_encode_text
        ImageVectorIndexService.encode_image = self.original_encode_image

        index_key = self.vector_service.build_user_index_key(self.user.id)
        for key in self.redis_keys:
            self.redis_client.delete(key)
        self.redis_client.delete(index_key)

        self.db.delete(self.user)
        self.db.commit()
        self.db.close()

    def _save_vector(self, oss_url: str, description: str, vector: list[float]) -> None:
        redis_key = self.vector_service.build_image_key(self.user.id, oss_url)
        index_key = self.vector_service.build_user_index_key(self.user.id)
        payload = {
            "userId": self.user.id,
            "ossUrl": oss_url,
            "description": description,
            "vector": vector,
            "vectorDimension": len(vector),
        }
        self.redis_client.set(redis_key, json.dumps(payload, ensure_ascii=False))
        self.redis_client.sadd(index_key, redis_key)
        self.redis_keys.append(redis_key)

    def test_search_by_text_returns_most_similar_image_first(self) -> None:
        response = self.client.post(
            "/api/file/search/text",
            json={"query": "白色休闲衬衫", "topK": 2},
            headers=self.headers,
        )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(200, body["code"])
        self.assertEqual(self.white_url, body["data"]["results"][0]["ossUrl"])
        self.assertGreater(body["data"]["results"][0]["score"], body["data"]["results"][1]["score"])

    def test_search_by_image_returns_most_similar_image_first(self) -> None:
        response = self.client.post(
            "/api/file/search/image",
            data={"topK": "2"},
            files={"file": ("query.png", b"fake-image-bytes", "image/png")},
            headers=self.headers,
        )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(200, body["code"])
        self.assertEqual(self.black_url, body["data"]["results"][0]["ossUrl"])
        self.assertGreater(body["data"]["results"][0]["score"], body["data"]["results"][1]["score"])


if __name__ == "__main__":
    unittest.main()
