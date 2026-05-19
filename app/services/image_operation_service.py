import base64
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from PIL import Image
from dashscope import MultiModalConversation

from app.core.config import settings


class ImageGenerationService:
    """负责调用图片编辑/合并模型。"""

    def edit_image(self, image: str, instruction: str) -> str:
        """根据一张图片和指令生成编辑后的图片地址。"""
        image_data = self._read_image_data(image)
        image_data_uri = self._to_data_uri(image_data)
        response = MultiModalConversation.call(
            api_key=settings.dashscope_api_key,
            model="qwen-image-2.0",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"image": image_data_uri},
                        {"text": instruction},
                    ],
                }
            ],
        )
        return self._extract_image_url(response)

    def merge_images(self, image1: str, image2: str, instruction: str) -> str:
        """根据两张图片和指令生成合并后的图片地址。"""
        image_data_uri1 = self._to_data_uri(self._read_image_data(image1))
        image_data_uri2 = self._to_data_uri(self._read_image_data(image2))
        response = MultiModalConversation.call(
            api_key=settings.dashscope_api_key,
            model="qwen-image-edit-plus",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"image": image_data_uri1},
                        {"image": image_data_uri2},
                        {"text": instruction},
                    ],
                }
            ],
        )
        return self._extract_image_url(response)

    def _read_image_data(self, image_url: str) -> bytes:
        """读取本地上传图片或远程图片的二进制内容。"""
        if image_url.startswith(settings.local_file_base_url):
            relative_path = image_url.removeprefix(settings.local_file_base_url).lstrip("/")
            local_path = settings.upload_dir / relative_path
            return local_path.read_bytes()

        parsed = urlparse(image_url)
        if parsed.scheme in {"http", "https"}:
            with urlopen(image_url, timeout=30) as response:
                return response.read()

        path = Path(image_url)
        if path.exists():
            return path.read_bytes()

        raise ValueError("图片地址无效，无法读取图片内容")

    def _to_data_uri(self, image_data: bytes) -> str:
        """把图片 bytes 转成多模态模型需要的 data URI。"""
        img = Image.open(BytesIO(image_data))
        image_format = (img.format or "png").lower()
        image_base64 = base64.b64encode(image_data).decode("utf-8")
        return f"data:image/{image_format};base64,{image_base64}"

    def _extract_image_url(self, response: object) -> str:
        """从 DashScope 返回值中提取图片地址。"""
        if not isinstance(response, dict):
            raise RuntimeError("模型返回结果格式不正确")

        choices = response.get("output", {}).get("choices") or []
        if not choices:
            raise RuntimeError("模型没有返回图片结果")

        content = choices[0].get("message", {}).get("content") or []
        if not content or not isinstance(content[0], dict):
            raise RuntimeError("模型返回内容为空")

        image_url = content[0].get("image")
        if not image_url:
            raise RuntimeError("模型未返回图片地址")

        return str(image_url)
