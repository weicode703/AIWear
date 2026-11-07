import base64
import hashlib
import json
import math
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from PIL import Image, ImageOps
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
    VALID_IMAGE_CATEGORIES = {"clothing", "person", "outfit", "other"}
    IMAGE_ATTRIBUTE_PROMPTS = {
        "category": {
            "clothing": "一张服装单品商品图，画面主要展示衣服本身，没有模特穿着",
            "person": "一张人物肖像或人像照片，重点是人的脸或上半身，不是服装商品图",
            "outfit": "一张模特穿着服装的全身穿搭图或试穿效果图",
            "other": "一张不属于服装或人物肖像的其他图片",
        },
        "color": {
            "black": "以黑色为主的服装",
            "white": "以白色为主的服装",
            "blue": "以蓝色为主的服装",
            "red": "以红色为主的服装",
            "green": "以绿色为主的服装",
            "yellow": "以黄色为主的服装",
            "pink": "以粉色为主的服装",
            "purple": "以紫色为主的服装",
            "gray": "以灰色为主的服装",
            "brown": "以棕色或咖啡色为主的服装",
        },
        "itemType": {
            "dress": "连衣裙或裙子",
            "shirt": "衬衫",
            "coat": "外套、大衣或夹克",
            "pants": "裤子",
            "top": "上衣、T恤或毛衣",
            "shoes": "鞋子或靴子",
            "bag": "包包",
        },
    }

    def __init__(self) -> None:
        # decode_responses=True 表示 Redis 返回字符串，方便直接 json.loads。
        self.redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

    def index_image(self, oss_url: str, user_id: int) -> ImageVectorIndexResponse:
        """先保存 CLIP 向量，再尽力补充描述，避免视觉模型故障让图片无法检索。"""
        image_data = self.read_image_data(oss_url)
        vector = self.encode_image(image_data)

        payload = {
            "userId": user_id,
            "ossUrl": oss_url,
            "imageHash": self.image_content_hash(image_data),
            "description": "",
            "imageCategory": "other",
            "imageAttributes": {"category": "other", "colors": [], "itemTypes": []},
            "vector": vector,
            "vectorDimension": len(vector),
            "model": "clip-vit-base-patch16",
            "descriptionModel": "qwen3.7-flash",
            "createdAt": datetime.now().isoformat(),
        }

        redis_key = self.build_image_key(user_id, oss_url)
        index_key = self.build_user_index_key(user_id)
        self.redis_client.set(redis_key, json.dumps(payload, ensure_ascii=False))
        self.redis_client.sadd(index_key, redis_key)

        description = ""
        try:
            qwen_image_input = self.build_qwen_image_input(oss_url, image_data)
            description, image_attributes = self.parse_image_metadata_response(
                self.describe_image(qwen_image_input)
            )
            payload["description"] = description
            payload["imageCategory"] = image_attributes["category"]
            payload["imageAttributes"] = image_attributes
            self.redis_client.set(redis_key, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:
            print(f"图片描述生成失败，已保留 CLIP 向量索引：{exc}")

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
        query_categories = self.infer_text_query_categories(query)
        results = self.search_similar_images(
            user_id=user_id,
            query_vector=query_vector,
            top_k=top_k,
            allowed_categories=query_categories,
            description_keywords=self.infer_description_keywords(query),
            query_text=query,
        )
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
        query_attributes = self.infer_query_image_attributes(query_vector)
        results = self.search_similar_images(
            user_id=user_id,
            query_vector=query_vector,
            top_k=top_k,
            exact_image_hash=self.image_content_hash(image_data),
            query_attributes=query_attributes,
            allow_low_score_fallback=False,
        )
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
        min_score: float | None = None,
        allowed_categories: list[str] | None = None,
        description_keywords: list[str] | None = None,
        query_text: str | None = None,
        exact_image_hash: str | None = None,
        query_attributes: dict | None = None,
        allow_low_score_fallback: bool = True,
    ) -> list[ImageSearchResultItem]:
        """从 Redis 读取当前用户的图片向量，并按余弦相似度排序。"""
        index_key = self.build_user_index_key(user_id)
        redis_keys = list(self.redis_client.smembers(index_key))
        if not redis_keys:
            return []

        pipeline = self.redis_client.pipeline(transaction=False)
        for redis_key in redis_keys:
            pipeline.get(redis_key)
        raw_values = pipeline.execute()

        strict_results: list[ImageSearchResultItem] = []
        threshold_results: list[ImageSearchResultItem] = []
        all_results: list[ImageSearchResultItem] = []
        result_categories: dict[str, str] = {}
        result_hashes: dict[str, str] = {}
        result_attributes: dict[str, dict] = {}
        rerank_scores: dict[str, float] = {}
        score_threshold = settings.image_search_min_score if min_score is None else min_score
        normalized_allowed_categories = (
            {
                category
                for category in (self.normalize_image_category(item) for item in allowed_categories)
                if category != "other"
            }
            if allowed_categories
            else set()
        )

        for redis_key, raw in zip(redis_keys, raw_values):
            if not raw:
                continue

            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(payload, dict):
                continue

            vector = payload.get("vector")
            if not isinstance(vector, list):
                continue

            try:
                stored_vector = [float(value) for value in vector]
            except (TypeError, ValueError):
                continue
            if (
                len(stored_vector) != len(query_vector)
                or not stored_vector
                or not all(math.isfinite(value) for value in stored_vector)
                or not any(stored_vector)
            ):
                continue

            score = self.cosine_similarity(query_vector, stored_vector)
            result = ImageSearchResultItem(
                redisKey=redis_key,
                ossUrl=str(payload.get("ossUrl", "")),
                description=str(payload.get("description", "")),
                score=round(score, 6),
            )
            all_results.append(result)

            description = result.description
            image_category = self.normalize_image_category(payload.get("imageCategory"))
            if image_category == "other":
                image_category = self.infer_image_category_from_description(description)
            result_categories[redis_key] = image_category
            result_hashes[redis_key] = str(payload.get("imageHash", ""))
            image_attributes = self.normalize_image_attributes(
                payload.get("imageAttributes"), description, image_category
            )
            result_attributes[redis_key] = image_attributes
            rerank_scores[redis_key] = score + self.image_attribute_score(
                query_attributes or {}, image_attributes
            )

            if score < score_threshold:
                continue
            threshold_results.append(result)

            if normalized_allowed_categories and image_category not in normalized_allowed_categories:
                continue

            if description_keywords and not self.description_matches_keywords(
                description,
                description_keywords,
            ):
                continue

            strict_results.append(result)

        aspect_groups = self.infer_query_aspect_groups(query_text or "")
        query_colors = self.normalize_attribute_values([query_text or ""], "color")
        query_item_types = self.normalize_attribute_values([query_text or ""], "itemType")
        aspect_results = [
            item
            for item in all_results
            if aspect_groups
            and all(self.description_matches_keywords(item.description, group) for group in aspect_groups)
        ]
        if query_colors:
            color_aspect_results = [
                item
                for item in aspect_results
                if set(result_attributes[item.redisKey]["colors"]) & set(query_colors)
            ]
            color_attribute_results = [
                item
                for item in all_results
                if set(result_attributes[item.redisKey]["colors"]) & set(query_colors)
                and (
                    not query_item_types
                    or set(result_attributes[item.redisKey]["itemTypes"]) & set(query_item_types)
                )
                and (
                    not normalized_allowed_categories
                    or result_categories[item.redisKey] in normalized_allowed_categories
                )
            ]
            # Exact description/attribute matches stay eligible even when CLIP's score is low.
            results = color_aspect_results or color_attribute_results
            if not results:
                # Legacy metadata may have a wrong category, but an explicit color and item
                # type in the description is still stronger evidence than an unrelated image.
                results = [
                    item
                    for item in all_results
                    if set(result_attributes[item.redisKey]["colors"]) & set(query_colors)
                    and (
                        not query_item_types
                        or set(result_attributes[item.redisKey]["itemTypes"])
                        & set(query_item_types)
                    )
                ]
        elif aspect_results:
            compatible_results = [
                item
                for item in aspect_results
                if (not normalized_allowed_categories or result_categories[item.redisKey] in normalized_allowed_categories)
                and (
                    not description_keywords
                    or self.description_matches_keywords(item.description, description_keywords)
                )
            ]
            results = compatible_results or aspect_results
        else:
            # Filters and the score floor improve precision when they match, but should not
            # turn uncertain CLIP/category/description guesses into an empty search page.
            results = strict_results or threshold_results or (
                all_results if allow_low_score_fallback else []
            )

        if exact_image_hash:
            exact_results = [
                item for item in all_results if result_hashes.get(item.redisKey) == exact_image_hash
            ]
        results.sort(key=lambda item: rerank_scores.get(item.redisKey, item.score), reverse=True)
        if exact_image_hash and exact_results:
            exact_keys = {item.redisKey for item in exact_results}
            results = exact_results + [item for item in results if item.redisKey not in exact_keys]

        unique_results = []
        seen_images = set()
        for item in results:
            image_identity = result_hashes.get(item.redisKey) or item.ossUrl or item.redisKey
            if image_identity in seen_images:
                continue
            seen_images.add(image_identity)
            unique_results.append(item)
        return unique_results[:top_k]

    def image_content_hash(self, image_data: bytes) -> str:
        """Hash decoded pixels so metadata or file encoding changes do not hide duplicates."""
        try:
            with Image.open(BytesIO(image_data)) as image:
                normalized = ImageOps.exif_transpose(image).convert("RGB")
                digest = hashlib.sha256()
                digest.update(normalized.width.to_bytes(4, "big"))
                digest.update(normalized.height.to_bytes(4, "big"))
                digest.update(normalized.tobytes())
                return digest.hexdigest()
        except Exception:
            return hashlib.sha256(image_data).hexdigest()

    def parse_image_metadata_response(self, response_text: str) -> tuple[str, dict]:
        """Read structured Qwen tags while remaining compatible with plain-text responses."""
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            data = None

        if isinstance(data, dict):
            description = str(data.get("description", "")).strip()
            category = self.normalize_image_category(data.get("category"))
            attributes = {
                "category": category,
                "colors": self.normalize_attribute_values(data.get("colors"), "color"),
                "itemTypes": self.normalize_attribute_values(data.get("itemTypes"), "itemType"),
            }
            inferred = self.extract_image_attributes(description)
            if category == "other":
                attributes["category"] = inferred["category"]
            for key in ("colors", "itemTypes"):
                attributes[key] = list(dict.fromkeys(attributes[key] + inferred[key]))
            return description or str(data.get("description", "")), attributes

        description = response_text.strip()
        return description, self.extract_image_attributes(description)

    def normalize_attribute_values(self, values: object, attribute_type: str) -> list[str]:
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            return []
        allowed = self.IMAGE_ATTRIBUTE_PROMPTS[attribute_type]
        aliases = {
            "color": {
                "黑色": "black", "黑": "black", "白色": "white", "白": "white",
                "蓝色": "blue", "蓝": "blue", "红色": "red", "红": "red",
                "绿色": "green", "绿": "green", "黄色": "yellow", "黄": "yellow",
                "粉色": "pink", "粉": "pink", "紫色": "purple", "紫": "purple",
                "灰色": "gray", "灰": "gray", "棕色": "brown", "咖色": "brown",
            },
            "itemType": {
                "连衣裙": "dress", "裙子": "dress", "裙": "dress", "衬衫": "shirt",
                "外套": "coat", "大衣": "coat", "夹克": "coat", "裤子": "pants",
                "裤": "pants", "上衣": "top", "t恤": "top", "毛衣": "top",
                "鞋子": "shoes", "鞋": "shoes", "靴子": "shoes", "包包": "bag", "包": "bag",
            },
        }.get(attribute_type, {})
        normalized = []
        for value in values:
            token = str(value).strip().lower()
            matches = [aliases.get(token, token)]
            if token not in aliases and token not in allowed:
                matches = [
                    aliases[alias]
                    for alias in sorted(aliases, key=len, reverse=True)
                    if alias.lower() in token
                ]
            for match in matches:
                if match in allowed and match not in normalized:
                    normalized.append(match)
        return normalized

    def extract_image_attributes(self, description: str) -> dict:
        colors = self.normalize_attribute_values([description], "color")
        item_types = self.normalize_attribute_values([description], "itemType")
        category = self.infer_image_category_from_description(description)
        return {"category": category, "colors": colors, "itemTypes": item_types}

    def normalize_image_attributes(
        self,
        attributes: object,
        description: str,
        fallback_category: str,
    ) -> dict:
        if not isinstance(attributes, dict):
            attributes = {}
        inferred = self.extract_image_attributes(description)
        category = self.normalize_image_category(attributes.get("category", fallback_category))
        if category == "other":
            category = inferred["category"]
        return {
            "category": category,
            "colors": list(dict.fromkeys(
                self.normalize_attribute_values(attributes.get("colors"), "color") + inferred["colors"]
            )),
            "itemTypes": list(dict.fromkeys(
                self.normalize_attribute_values(attributes.get("itemTypes"), "itemType") + inferred["itemTypes"]
            )),
        }

    def image_attribute_score(self, query_attributes: dict, image_attributes: dict) -> float:
        """Use uncertain visual labels as small ranking hints, never as hard filters."""
        bonus = 0.0
        query_category = query_attributes.get("category")
        image_category = image_attributes.get("category")
        if query_category in self.VALID_IMAGE_CATEGORIES - {"other"}:
            bonus += 0.06 if query_category == image_category else -0.025

        for key, matching_bonus, mismatch_penalty in (
            ("colors", 0.08, 0.035),
            ("itemTypes", 0.08, 0.025),
        ):
            query_values = set(query_attributes.get(key, []))
            image_values = set(image_attributes.get(key, []))
            if query_values and image_values:
                bonus += matching_bonus if query_values & image_values else -mismatch_penalty
        return bonus

    def infer_query_image_attributes(self, query_vector: list[float]) -> dict:
        """Classify broad image attributes in one local CLIP text batch for reranking."""
        try:
            labels = []
            prompts = []
            for group_name, group in self.IMAGE_ATTRIBUTE_PROMPTS.items():
                for label, prompt in group.items():
                    labels.append((group_name, label))
                    prompts.append(prompt)
            text_vectors = self.encode_text_batch(prompts)
        except Exception as exc:
            print(f"查询图片属性识别失败，改用 CLIP 相似度排序：{exc}")
            return {}

        grouped_scores: dict[str, list[tuple[str, float]]] = {}
        for (group_name, label), vector in zip(labels, text_vectors):
            grouped_scores.setdefault(group_name, []).append(
                (label, self.cosine_similarity(query_vector, vector))
            )

        attributes = {"category": "other", "colors": [], "itemTypes": []}
        output_keys = {"category": "category", "color": "colors", "itemType": "itemTypes"}
        for group_name, scores in grouped_scores.items():
            scores.sort(key=lambda item: item[1], reverse=True)
            if not scores:
                continue
            best_label, best_score = scores[0]
            margin = best_score - scores[1][1] if len(scores) > 1 else 1.0
            if best_score < 0.16 or margin < 0.008:
                continue
            key = output_keys[group_name]
            attributes[key] = best_label if group_name == "category" else [best_label]
        return attributes

    def infer_query_aspect_groups(self, query: str) -> list[list[str]]:
        """提取可直接从图片描述验证的颜色、服装和风格词。"""
        if not query.strip():
            return []

        aspect_groups = [
            ["红", "红色", "鲜红", "正红", "酒红", "枣红", "玫红", "朱红", "绯红"],
            ["橙", "橙色", "橘色", "橘红"],
            ["黄", "黄色", "鹅黄", "姜黄"],
            ["绿", "绿色", "墨绿", "军绿", "草绿"],
            ["蓝", "蓝色", "浅蓝", "深蓝", "藏蓝", "天蓝"],
            ["紫", "紫色", "浅紫", "深紫"],
            ["粉", "粉色", "浅粉", "玫粉"],
            ["白", "白色", "米白", "奶白", "象牙白"],
            ["黑", "黑色", "纯黑"],
            ["灰", "灰色", "银灰"],
            ["棕", "棕色", "咖色", "咖啡色"],
            ["裙", "裙子", "连衣裙", "半身裙", "百褶裙", "礼服"],
            ["衬衫", "衬衣"],
            ["外套", "大衣", "风衣", "夹克"],
            ["裤", "裤子", "牛仔裤", "西裤", "短裤"],
            ["上衣", "T恤", "针织衫", "毛衣"],
            ["鞋", "鞋子", "靴子"],
            ["包", "包包", "手提包", "挎包"],
            ["休闲", "休闲风"],
            ["通勤", "职场", "商务"],
            ["运动", "运动风"],
            ["复古", "复古风"],
            ["优雅", "优雅风"],
        ]
        return [group for group in aspect_groups if self.contains_any(query, group)]

    def infer_text_query_categories(self, query: str) -> list[str] | None:
        """根据搜索文字判断应该搜索衣服、人物，还是人物穿搭图。"""
        has_person = self.contains_any(query, self.person_keywords())
        has_wearing = self.contains_any(query, ["穿", "穿着", "试穿", "上身", "搭配", "效果"])
        has_clothing = self.contains_any(query, self.clothing_keywords())

        if has_person and (has_wearing or has_clothing):
            return ["outfit"]
        if has_person:
            return ["person"]
        if has_clothing:
            return ["clothing"]
        return None

    def infer_image_category_from_vector(self, query_vector: list[float]) -> str:
        """用 CLIP 零样本文本提示估计查询图片类型。"""
        category_prompts = {
            "clothing": "服装单品 商品图 衣服 裙子 衬衫 裤子 外套",
            "person": "人物头像 人脸 半身照 肖像照片",
            "outfit": "人物穿着服装 全身穿搭 试穿效果 模特上身图",
            "other": "其他图片 背景 场景",
        }
        scores = {
            category: self.cosine_similarity(query_vector, self.encode_text(prompt))
            for category, prompt in category_prompts.items()
        }
        return max(scores, key=scores.get)

    def infer_image_category_from_description(self, description: str) -> str:
        """根据图片描述兜底判断图片类型，兼容 Redis 里已经存在的老数据。"""
        has_person = self.contains_any(description, self.person_keywords())
        has_clothing = self.contains_any(description, self.clothing_keywords())
        has_wearing = self.contains_any(description, ["穿", "穿着", "试穿", "上身", "搭配", "合身"])

        if has_person and (has_wearing or has_clothing):
            return "outfit"
        if has_person:
            return "person"
        if has_clothing:
            return "clothing"
        return "other"

    def normalize_image_category(self, category: object) -> str:
        """标准化图片类型，避免脏数据影响过滤。"""
        category_text = str(category or "").strip().lower()
        if category_text in self.VALID_IMAGE_CATEGORIES:
            return category_text
        return "other"

    def contains_any(self, text: str, keywords: list[str]) -> bool:
        """判断文本中是否包含任一关键词。"""
        return any(keyword in text for keyword in keywords)

    def clothing_keywords(self) -> list[str]:
        """服装品类关键词。"""
        return [
            "衣服",
            "服装",
            "裙",
            "裙子",
            "连衣裙",
            "半身裙",
            "短裙",
            "长裙",
            "百褶裙",
            "衬衫",
            "衬衣",
            "外套",
            "大衣",
            "风衣",
            "夹克",
            "裤",
            "裤子",
            "长裤",
            "短裤",
            "牛仔裤",
            "西裤",
            "上衣",
            "T恤",
            "针织衫",
            "毛衣",
            "西装",
            "帽",
            "帽子",
            "鞋",
            "鞋子",
            "靴",
            "靴子",
            "包",
            "包包",
            "手提包",
            "挎包",
        ]

    def person_keywords(self) -> list[str]:
        """人物相关关键词。"""
        return [
            "人",
            "人物",
            "女生",
            "女性",
            "女士",
            "女孩",
            "男生",
            "男性",
            "男士",
            "男孩",
            "模特",
            "头像",
            "脸",
            "人像",
            "半身",
            "全身",
        ]

    def infer_description_keywords(self, query: str) -> list[str]:
        """根据搜索词提取服装品类词，用图片描述做二次过滤。"""
        keyword_groups = [
            ["裙", "裙子", "连衣裙", "半身裙", "短裙", "长裙", "百褶裙"],
            ["衬衫", "衬衣"],
            ["外套", "大衣", "风衣", "夹克"],
            ["裤", "裤子", "长裤", "短裤", "牛仔裤", "西裤"],
            ["上衣", "T恤", "针织衫", "毛衣"],
            ["帽", "帽子"],
            ["鞋", "鞋子", "靴", "靴子"],
            ["包", "包包", "手提包", "挎包"],
        ]

        matched: list[str] = []
        for group in keyword_groups:
            if any(keyword in query for keyword in group):
                matched.extend(group)

        return list(dict.fromkeys(matched))

    def description_matches_keywords(self, description: str, keywords: list[str]) -> bool:
        """描述里包含任一服装品类词，才认为和该品类搜索相关。"""
        return any(keyword in description for keyword in keywords)

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
        """调用视觉模型获取图片描述（直连 DashScope，避免 LangChain 包装层改写图片参数）。"""
        if not settings.dashscope_api_key:
            raise RuntimeError("缺少 DASHSCOPE_API_KEY，无法调用视觉模型生成图片描述")

        import dashscope
        from dashscope import MultiModalConversation

        if settings.dashscope_base_http_api_url:
            dashscope.base_http_api_url = settings.dashscope_base_http_api_url

        response = MultiModalConversation.call(
            api_key=settings.dashscope_api_key,
            model="qwen3.7-flash",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"image": image_input},
                        {
                            "text": (
                                "请识别图片并只返回一个 JSON 对象，不要 Markdown。字段为："
                                "description（中文简述），category（clothing/person/outfit/other），"
                                "colors（数组，只能含 black/white/blue/red/green/yellow/pink/purple/gray/brown），"
                                "itemTypes（数组，只能含 dress/shirt/coat/pants/top/shoes/bag）。"
                                "人物穿着服装的图片 category 用 outfit；纯服装商品图用 clothing。"
                                "看不清的属性返回空数组，不要猜。"
                            )
                        },
                    ],
                }
            ],
        )

        if getattr(response, "status_code", 200) != 200:
            raise RuntimeError(
                f"视觉模型调用失败：{response.status_code} {response.code} {response.message}"
            )

        choices = response.output.choices or []
        if not choices:
            raise RuntimeError("视觉模型没有返回内容")

        return self.extract_text(choices[0].message.content)

    def encode_text(self, text: str) -> list[float]:
        """调用本地 CLIP 模型，把文字转换成向量。"""
        return self.encode_text_batch([text])[0]

    def encode_text_batch(self, texts: list[str]) -> list[list[float]]:
        """用一次 CLIP 前向计算编码多条文本，供图像属性判断复用。"""
        model, processor = self.load_clip_model()

        import torch

        inputs = processor(text=texts, return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            features = self.extract_feature_tensor(model.get_text_features(**inputs))
            features = features / features.norm(dim=-1, keepdim=True)

        return [[float(value) for value in vector] for vector in features.cpu().tolist()]

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
