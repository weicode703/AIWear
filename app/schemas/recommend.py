from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    """定义 /recommend 接口的请求体结构。"""

    scene: str = Field(..., description="Where the user is going")
    weather: str = Field(..., description="Weather information")
    style: str = Field(..., description="Preferred style")
    gender: str | None = Field(default=None, description="Optional gender hint")
    owned_items: list[str] = Field(default_factory=list, description="Items the user already has")


class RecommendResponse(BaseModel):
    """定义 /recommend 接口返回的数据结构。"""

    summary: str
    outfit_items: list[str]
    reasons: list[str]
    alternatives: list[str]
    avoid_tips: list[str]
    model_source: str
