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


class ImageVectorIndexApiTest(unittest.TestCase):
    """验证图片描述和 CLIP 向量可以按用户维度保存到 Redis。"""

    def setUp(self) -> None:
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        self.db = SessionLocal()
        self.redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

        username = f"vector_user_{uuid.uuid4().hex}"
        self.user = User(username=username, email=f"{username}@example.com")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.token = JwtService().generate_token(self.user)
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.oss_url = f"https://oss.example.com/{uuid.uuid4().hex}.png"

        self.original_read_image_data = ImageVectorIndexService.read_image_data
        self.original_describe_image = ImageVectorIndexService.describe_image
        self.original_encode_image = ImageVectorIndexService.encode_image
        ImageVectorIndexService.read_image_data = lambda _self, _url: b"fake-image-bytes"
        ImageVectorIndexService.describe_image = lambda _self, _url: "白色衬衫，浅色牛仔裤，休闲风格"
        ImageVectorIndexService.encode_image = lambda _self, _image_data: [0.1, 0.2, 0.3]

    def tearDown(self) -> None:
        ImageVectorIndexService.read_image_data = self.original_read_image_data
        ImageVectorIndexService.describe_image = self.original_describe_image
        ImageVectorIndexService.encode_image = self.original_encode_image

        service = ImageVectorIndexService()
        redis_key = service.build_image_key(self.user.id, self.oss_url)
        index_key = service.build_user_index_key(self.user.id)
        self.redis_client.delete(redis_key)
        self.redis_client.delete(index_key)

        self.db.delete(self.user)
        self.db.commit()
        self.db.close()

    def test_index_image_vector_saves_json_to_redis(self) -> None:
        response = self.client.post(
            "/api/file/index-image-vector",
            json={"ossUrl": self.oss_url, "userId": self.user.id},
            headers=self.headers,
        )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(200, body["code"])
        self.assertEqual(3, body["data"]["vectorDimension"])

        redis_key = body["data"]["redisKey"]
        payload = json.loads(self.redis_client.get(redis_key))
        self.assertEqual(self.user.id, payload["userId"])
        self.assertEqual(self.oss_url, payload["ossUrl"])
        self.assertEqual("白色衬衫，浅色牛仔裤，休闲风格", payload["description"])
        self.assertEqual([0.1, 0.2, 0.3], payload["vector"])
        self.assertTrue(self.redis_client.sismember(f"image:vector:index:{self.user.id}", redis_key))


if __name__ == "__main__":
    unittest.main()
