from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.services.llm_service import LLMService


class RecommendationService:
    """负责组织推荐流程的服务类。"""

    def __init__(self) -> None:
        """初始化推荐服务，并准备一个 LLM 服务对象。"""
        self.llm_service = LLMService()

    def recommend(self, request: RecommendRequest) -> RecommendResponse:
        """推荐主流程：准备 prompt，调用模型，清洗结果，再组装响应。"""
        fallback_data = self._build_fallback_result(request)
        prompt = self._build_prompt(request)
        result, model_source = self.llm_service.generate_recommendation(prompt, fallback_data)
        clean_result = self._normalize_result(result, fallback_data)

        return RecommendResponse(
            summary=clean_result["summary"],
            outfit_items=clean_result["outfit_items"],
            reasons=clean_result["reasons"],
            alternatives=clean_result["alternatives"],
            avoid_tips=clean_result["avoid_tips"],
            model_source=model_source,
        )

    def _build_prompt(self, request: RecommendRequest) -> str:
        """把用户输入整理成提示词，交给 LLM 生成推荐结果。"""
        owned_items_text = ", ".join(request.owned_items) if request.owned_items else "none"

        return (
            "You are helping with outfit recommendation.\n"
            "Please return one practical outfit plan.\n"
            "The result must be easy for beginners to read.\n"
            "Return JSON only.\n\n"
            "[User Info]\n"
            f"Scene: {request.scene}\n"
            f"Weather: {request.weather}\n"
            f"Style: {request.style}\n"
            f"Gender hint: {request.gender or 'not provided'}\n"
            f"Owned items: {owned_items_text}\n\n"
            "[Output Rules]\n"
            "1. summary: one short paragraph\n"
            "2. outfit_items: a list of recommended clothing items\n"
            "3. reasons: explain why the outfit works\n"
            "4. alternatives: provide backup choices\n"
            "5. avoid_tips: provide simple mistakes to avoid"
        )

    def _normalize_result(self, result: dict, fallback_data: dict) -> dict:
        """清洗模型返回值，保证字段完整，格式稳定。"""
        summary = result.get("summary") or fallback_data["summary"]
        outfit_items = self._ensure_string_list(result.get("outfit_items"), fallback_data["outfit_items"])
        reasons = self._ensure_string_list(result.get("reasons"), fallback_data["reasons"])
        alternatives = self._ensure_string_list(result.get("alternatives"), fallback_data["alternatives"])
        avoid_tips = self._ensure_string_list(result.get("avoid_tips"), fallback_data["avoid_tips"])

        return {
            "summary": str(summary),
            "outfit_items": outfit_items,
            "reasons": reasons,
            "alternatives": alternatives,
            "avoid_tips": avoid_tips,
        }

    def _ensure_string_list(self, value: object, default: list[str]) -> list[str]:
        """确保某个字段最终一定是非空的字符串列表。"""
        if not isinstance(value, list):
            return default

        clean_items = [str(item).strip() for item in value if str(item).strip()]
        return clean_items or default

    def _build_fallback_result(self, request: RecommendRequest) -> dict:
        """当没有真实模型时，使用规则生成一个最小可用的推荐结果。"""
        owned_items_lower = [item.lower() for item in request.owned_items]

        top = "white shirt" if "white shirt" in owned_items_lower else "clean solid-color top"
        bottom = "black trousers" if "black trousers" in owned_items_lower else "straight-leg dark trousers"
        outer = "beige trench coat" if "beige trench coat" in owned_items_lower else "lightweight jacket"
        shoes = "clean loafers or simple sneakers"

        return {
            "summary": (
                f"For {request.scene}, a {request.style} outfit that matches {request.weather} "
                "should stay neat, comfortable, and easy to adjust."
            ),
            "outfit_items": [top, bottom, outer, shoes],
            "reasons": [
                "The color combination is simple and easy to control.",
                "Layering helps handle temperature changes.",
                "The outfit balances practicality and presentability.",
            ],
            "alternatives": [
                "Swap the outer layer for a cardigan if the weather feels warmer.",
                "Use a knit top instead of a shirt for a softer look.",
            ],
            "avoid_tips": [
                "Avoid using too many bright colors in one outfit.",
                "Avoid heavy layers if the temperature is mild.",
            ],
        }
