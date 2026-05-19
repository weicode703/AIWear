from fastapi import APIRouter

from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.services.recommendation_service import RecommendationService


# APIRouter 用来集中管理一组接口。
router = APIRouter()

# 创建推荐服务对象，路由函数里直接调用它完成业务处理。
recommendation_service = RecommendationService()


@router.post("/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest) -> RecommendResponse:
    """接收用户穿搭需求，并返回结构化的推荐结果。"""
    return recommendation_service.recommend(request)
