from app.services.image_vector_service import ImageVectorIndexService


class EmbeddingService:
    """文本向量服务。

    当前复用本地 CLIP 的文本编码能力，输出 512 维向量。
    """

    def __init__(self) -> None:
        self.image_vector_service = ImageVectorIndexService()

    def encode_text(self, text: str) -> list[float]:
        """把一段文本转换为向量，用于 RAG 检索。"""
        return self.image_vector_service.encode_text(text)
