from datetime import datetime

from pydantic import BaseModel, Field


class FileResponse(BaseModel):
    """返回给前端的文件信息。"""

    id: int
    fileName: str = Field(..., description="原始文件名")
    fileType: str = Field(..., description="文件类型，例如 image")
    ossUrl: str = Field(..., description="文件访问地址；本地模式下也复用这个字段")
    url: str = Field(..., description="文件访问地址")
    filePath: str = Field(..., description="兼容前端搜索结果使用的文件地址")
    storageBackend: str = Field(..., description="存储方式：local 或 oss")
    createdAt: datetime
    vectorIndexed: bool | None = Field(None, description="是否已经写入图片向量索引")
    vectorIndexError: str | None = Field(None, description="图片向量入库失败原因")


class EditImageRequest(BaseModel):
    """图片编辑请求。"""

    image: str = Field(..., description="要编辑的图片地址")
    instruction: str = Field(..., description="编辑指令")


class MergeImageRequest(BaseModel):
    """图片合并请求。"""

    image1: str = Field(..., description="第一张图片地址")
    image2: str = Field(..., description="第二张图片地址")
    instruction: str = Field(..., description="合并指令")


class ImageVectorIndexRequest(BaseModel):
    """图片向量入库请求。"""

    ossUrl: str = Field(..., description="图片 OSS 地址或本地访问地址")
    userId: int = Field(..., description="图片所属用户 ID")


class ImageVectorIndexResponse(BaseModel):
    """图片向量入库结果。"""

    redisKey: str = Field(..., description="图片向量 JSON 在 Redis 中的 key")
    userId: int = Field(..., description="图片所属用户 ID")
    ossUrl: str = Field(..., description="图片地址")
    description: str = Field(..., description="Qwen-VL-Max 生成的图片描述")
    vectorDimension: int = Field(..., description="CLIP 图片向量维度，正常应为 512")


class TextImageSearchRequest(BaseModel):
    """文搜图请求。"""

    query: str = Field(..., description="用户输入的搜索文字，例如：白色衬衫")
    topK: int = Field(10, ge=1, le=50, description="最多返回多少条相似图片")


class ImageSearchResultItem(BaseModel):
    """单条图片搜索结果。"""

    redisKey: str = Field(..., description="结果在 Redis 中的 key")
    ossUrl: str = Field(..., description="图片地址")
    description: str = Field("", description="图片描述")
    score: float = Field(..., description="相似度分数，越接近 1 越相似")


class ImageSearchResponse(BaseModel):
    """文搜图/图搜图响应结果。"""

    queryType: str = Field(..., description="搜索类型：text 或 image")
    total: int = Field(..., description="返回结果数量")
    results: list[ImageSearchResultItem] = Field(default_factory=list)


class ImageOperationResponse(BaseModel):
    """图片编辑/合并结果。"""

    id: int
    action: str
    url: str
    saved_oss_url: str
    saveUrl: str
    outputOssUrl: str


class RecordResponse(BaseModel):
    """历史记录响应结构。"""

    id: int
    action: str
    inputOssUrl1: str | None = None
    inputOssUrl2: str | None = None
    instruction: str | None = None
    outputOssUrl: str | None = None
    createdAt: datetime | None = None
