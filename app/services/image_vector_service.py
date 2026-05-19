import base64
import hashlib
import json
import math
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from PIL import Image
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage
from redis import Redis

from app.core.config import settings
from app.schemas.file import (
    ImageSearchResponse,
    ImageSearchResultItem,
    ImageVectorIndexResponse,
)


class ImageVectorIndexService:
    """图片向量服务。

    这个类同时负责三件事：
    1. 图片向量入库：图片描述 + CLIP 图片向量保存到 Redis；
    2. 文搜图：把文字转成 CLIP 文本向量，再和 Redis 图片向量比相似度；
    3. 图搜图：把查询图片转成 CLIP 图片向量，再和 Redis 图片向量比相似度。
    """

    _clip_model = None
    _clip_processor = None

    def __init__(self) -> None:
        # decode_responses=True 表示 Redis 返回字符串，方便直接 json.loads。
        self.redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

    def index_image(self, oss_url: str, user_id: int) -> ImageVectorIndexResponse:
        """生成图片描述和图片向量，并写入 Redis。"""
        image_data = self.read_image_data(oss_url)
        qwen_image_input = self.build_qwen_image_input(oss_url, image_data)
        description = self.describe_image(qwen_image_input)
        vector = self.encode_image(image_data)

        payload = {
            "userId": user_id,
            "ossUrl": oss_url,
            "description": description,
            "vector": vector,
            "vectorDimension": len(vector),
            "model": "clip-vit-base-patch16",
            "descriptionModel": "qwen-vl-max",
            "createdAt": datetime.now().isoformat(),
        }

        redis_key = self.build_image_key(user_id, oss_url)
        index_key = self.build_user_index_key(user_id)
        self.redis_client.set(redis_key, json.dumps(payload, ensure_ascii=False))
        self.redis_client.sadd(index_key, redis_key)

        return ImageVectorIndexResponse(
            redisKey=redis_key,
            userId=user_id,
            ossUrl=oss_url,
            description=description,
            vectorDimension=len(vector),
        )

    def search_by_text(self, user_id: int, query: str, top_k: int = 10) -> ImageSearchResponse:
        """文搜图：把搜索文字转成向量，然后查找相似图片。"""
        if not query.strip():
            raise ValueError("搜索文字不能为空")

        query_vector = self.encode_text(query)
        results = self.search_similar_images(user_id=user_id, query_vector=query_vector, top_k=top_k)
        return ImageSearchResponse(queryType="text", total=len(results), results=results)

    def search_by_image_data(
        self,
        user_id: int,
        image_data: bytes,
        top_k: int = 10,
    ) -> ImageSearchResponse:
        """图搜图：把上传的查询图片转成向量，然后查找相似图片。"""
        if not image_data:
            raise ValueError("查询图片不能为空")

        query_vector = self.encode_image(image_data)
        results = self.search_similar_images(user_id=user_id, query_vector=query_vector, top_k=top_k)
        return ImageSearchResponse(queryType="image", total=len(results), results=results)

    def search_by_image_url(
        self,
        user_id: int,
        image_url: str,
        top_k: int = 10,
    ) -> ImageSearchResponse:
        """图搜图：根据图片地址读取图片，再查找相似图片。"""
        if not image_url.strip():
            raise ValueError("图片地址不能为空")

        image_data = self.read_image_data(image_url)
        return self.search_by_image_data(user_id=user_id, image_data=image_data, top_k=top_k)

    def search_similar_images(
        self,
        user_id: int,
        query_vector: list[float],
        top_k: int,
    ) -> list[ImageSearchResultItem]:
        """从 Redis 读取当前用户的图片向量，并按余弦相似度排序。"""
        index_key = self.build_user_index_key(user_id)
        redis_keys = self.redis_client.smembers(index_key)
        results: list[ImageSearchResultItem] = []

        for redis_key in redis_keys:
            raw = self.redis_client.get(redis_key)
            if not raw:
                continue

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            vector = payload.get("vector")
            if not isinstance(vector, list):
                continue

            score = self.cosine_similarity(query_vector, [float(value) for value in vector])
            results.append(
                ImageSearchResultItem(
                    redisKey=redis_key,
                    ossUrl=str(payload.get("ossUrl", "")),
                    description=str(payload.get("description", "")),
                    score=round(score, 6),
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    def cosine_similarity(self, vector_a: list[float], vector_b: list[float]) -> float:
        """计算两个向量的余弦相似度，越接近 1 表示越相似。"""
        if not vector_a or not vector_b or len(vector_a) != len(vector_b):
            return 0.0

        dot = sum(a * b for a, b in zip(vector_a, vector_b))
        norm_a = math.sqrt(sum(a * a for a in vector_a))
        norm_b = math.sqrt(sum(b * b for b in vector_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    def build_image_key(self, user_id: int, oss_url: str) -> str:
        """生成单张图片在 Redis 中的 key。"""
        url_hash = hashlib.sha256(oss_url.encode("utf-8")).hexdigest()
        return f"image:vector:{user_id}:{url_hash}"

    def build_user_index_key(self, user_id: int) -> str:
        """生成当前用户的图片向量索引集合 key。"""
        return f"image:vector:index:{user_id}"

    def build_qwen_image_input(self, oss_url: str, image_data: bytes) -> str:
        """生成 Qwen-VL 可以读取的图片输入。"""
        if oss_url.startswith("data:image/"):
            return oss_url

        parsed = urlparse(oss_url)
        if parsed.scheme in {"http", "https"}:
            return oss_url

        return self.image_bytes_to_data_uri(image_data)

    def image_bytes_to_data_uri(self, image_data: bytes) -> str:
        """把图片二进制内容转换成 data URI。"""
        image = Image.open(BytesIO(image_data))
        image_format = (image.format or "png").lower()
        image_base64 = base64.b64encode(image_data).decode("utf-8")
        return f"data:image/{image_format};base64,{image_base64}"

    def describe_image(self, image_input: str) -> str:
        """调用 Qwen-VL-Max 获取图片描述。"""
        if not settings.dashscope_api_key:
            raise RuntimeError("缺少 DASHSCOPE_API_KEY，无法调用 Qwen-VL-Max 生成图片描述")

        model = ChatTongyi(
            model_name="qwen-vl-max",
            temperature=0.0,
            dashscope_api_key=settings.dashscope_api_key,
        )
        response = model.invoke(
            [
                HumanMessage(
                    content=[
                        {"image": image_input},
                        {
                            "text": (
                                "请用一句中文简要描述这张图片的服装、人物、颜色、风格和场景，"
                                "最后给出 3 到 5 个关键词，用逗号分隔。"
                            )
                        },
                    ]
                )
            ]
        )
        return self.extract_text(response.content)

    def encode_text(self, text: str) -> list[float]:
        """调用本地 CLIP 模型，把文字转换成向量。"""
        model, processor = self.load_clip_model()

        import torch

        inputs = processor(text=[text], return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            features = self.extract_feature_tensor(model.get_text_features(**inputs))
            features = features / features.norm(dim=-1, keepdim=True)

        vector = features[0].cpu().tolist()
        return [float(value) for value in vector]

    def encode_image(self, image_data: bytes) -> list[float]:
        """调用本地 CLIP 模型，把图片转换成向量。"""
        model, processor = self.load_clip_model()
        image = Image.open(BytesIO(image_data)).convert("RGB")

        import torch

        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            features = self.extract_feature_tensor(model.get_image_features(**inputs))
            features = features / features.norm(dim=-1, keepdim=True)

        vector = features[0].cpu().tolist()
        return [float(value) for value in vector]

    def extract_feature_tensor(self, model_output):
        """兼容不同 transformers 版本，提取真正用于相似度计算的向量 Tensor。

        有些版本的 CLIPModel.get_image_features/get_text_features 直接返回 Tensor；
        你当前版本返回 BaseModelOutputWithPooling，向量在 pooler_output 字段里。
        """
        if hasattr(model_output, "norm"):
            return model_output

        if hasattr(model_output, "pooler_output"):
            return model_output.pooler_output

        if isinstance(model_output, (tuple, list)) and model_output:
            return model_output[0]

        raise RuntimeError("CLIP 模型返回结果中没有找到可用的向量 Tensor")

    def load_clip_model(self):
        """懒加载本地 CLIP 模型，避免 FastAPI 启动时就加载大模型。"""
        if self.__class__._clip_model is not None and self.__class__._clip_processor is not None:
            return self.__class__._clip_model, self.__class__._clip_processor

        if not settings.clip_model_dir.exists() or not any(settings.clip_model_dir.iterdir()):
            raise RuntimeError(
                f"本地 CLIP 模型目录为空：{settings.clip_model_dir}。"
                "请先使用 modelscope snapshot_download 下载模型。"
            )

        try:
            from transformers import CLIPModel, CLIPProcessor
        except ImportError as exc:
            raise RuntimeError("缺少 transformers 依赖，请先执行 pip install transformers") from exc

        self.__class__._clip_model = CLIPModel.from_pretrained(str(settings.clip_model_dir))
        self.__class__._clip_processor = CLIPProcessor.from_pretrained(str(settings.clip_model_dir))
        self.__class__._clip_model.eval()
        return self.__class__._clip_model, self.__class__._clip_processor

    def read_image_data(self, image_url: str) -> bytes:
        """读取 OSS、本地 uploads 地址、data URI 或本地文件路径中的图片内容。"""
        if image_url.startswith("data:image/"):
            _, base64_data = image_url.split(",", 1)
            return base64.b64decode(base64_data)

        if image_url.startswith(settings.local_file_base_url):
            relative_path = image_url.removeprefix(settings.local_file_base_url).lstrip("/")
            return (settings.upload_dir / relative_path).read_bytes()

        parsed = urlparse(image_url)
        if parsed.scheme in {"http", "https"}:
            with urlopen(image_url, timeout=30) as response:
                return response.read()

        local_path = Path(image_url)
        if local_path.exists():
            return local_path.read_bytes()

        raise ValueError("图片地址无效，无法读取图片内容")

    def extract_text(self, content: object) -> str:
        """兼容不同模型返回格式，提取文本内容。"""
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("text"):
                    parts.append(str(item["text"]))
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts).strip()

        return str(content or "").strip()
