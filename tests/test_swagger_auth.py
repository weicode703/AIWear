import unittest

from fastapi.testclient import TestClient

from app.main import app


class SwaggerAuthTest(unittest.TestCase):
    """验证 Swagger 授权窗口使用简单 Bearer Token，而不是用户名密码表单。"""

    def test_openapi_uses_http_bearer_auth(self) -> None:
        client = TestClient(app)
        schema = client.get("/openapi.json").json()
        security_schemes = schema["components"]["securitySchemes"]

        self.assertIn("HTTPBearer", security_schemes)
        self.assertEqual("http", security_schemes["HTTPBearer"]["type"])
        self.assertEqual("bearer", security_schemes["HTTPBearer"]["scheme"])


if __name__ == "__main__":
    unittest.main()
