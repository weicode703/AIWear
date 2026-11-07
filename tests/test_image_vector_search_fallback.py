import json
import unittest

from app.services.image_vector_service import ImageVectorIndexService


class MemoryPipeline:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.keys = []

    def get(self, key):
        self.keys.append(key)
        return self

    def execute(self):
        return [self.redis_client.values.get(key) for key in self.keys]


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.sets = {}

    def set(self, key, value):
        self.values[key] = value

    def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(value)

    def smembers(self, key):
        return self.sets.get(key, set())

    def pipeline(self, transaction=False):
        return MemoryPipeline(self)


class ImageVectorSearchFallbackTest(unittest.TestCase):
    def setUp(self):
        self.service = ImageVectorIndexService.__new__(ImageVectorIndexService)
        self.service.redis_client = MemoryRedis()

    def _add_image(
        self,
        user_id,
        url,
        vector,
        description="",
        category="other",
        image_hash="",
        image_attributes=None,
    ):
        key = self.service.build_image_key(user_id, url)
        index_key = self.service.build_user_index_key(user_id)
        self.service.redis_client.set(
            key,
            json.dumps(
                {
                    "userId": user_id,
                    "ossUrl": url,
                    "description": description,
                    "imageCategory": category,
                    "imageHash": image_hash,
                    "imageAttributes": image_attributes or {},
                    "vector": vector,
                }
            ),
        )
        self.service.redis_client.sadd(index_key, key)
        return key

    def test_search_falls_back_when_category_and_description_filters_miss(self):
        url = "https://example.com/dress.png"
        key = self._add_image(7, url, [1.0, 0.0], category="person")

        results = self.service.search_similar_images(
            user_id=7,
            query_vector=[1.0, 0.0],
            top_k=5,
            allowed_categories=["clothing"],
            description_keywords=["裙子"],
        )

        self.assertEqual([key], [item.redisKey for item in results])

    def test_search_falls_back_below_configured_score_floor(self):
        url = "https://example.com/coat.png"
        key = self._add_image(8, url, [0.1, 0.995])

        results = self.service.search_similar_images(
            user_id=8,
            query_vector=[1.0, 0.0],
            top_k=5,
            min_score=0.5,
        )

        self.assertEqual([key], [item.redisKey for item in results])

    def test_image_search_does_not_return_candidates_below_relevance_floor(self):
        self._add_image(14, "https://example.com/weak-match.png", [0.1, 0.995])

        results = self.service.search_similar_images(
            user_id=14,
            query_vector=[1.0, 0.0],
            top_k=10,
            min_score=0.5,
            allow_low_score_fallback=False,
        )

        self.assertEqual([], results)

    def test_exact_image_match_is_first_even_below_score_floor(self):
        exact_key = self._add_image(
            12,
            "https://example.com/original.png",
            [0.1, 0.995],
            image_hash="same-decoded-image",
        )
        similar_key = self._add_image(
            12,
            "https://example.com/similar.png",
            [1.0, 0.0],
        )

        results = self.service.search_similar_images(
            user_id=12,
            query_vector=[1.0, 0.0],
            top_k=5,
            min_score=0.9,
            exact_image_hash="same-decoded-image",
        )

        self.assertEqual(exact_key, results[0].redisKey)
        self.assertIn(similar_key, [item.redisKey for item in results])

    def test_image_content_hash_ignores_png_metadata(self):
        from io import BytesIO

        from PIL import Image, PngImagePlugin

        pixels = Image.new("RGB", (2, 2), (20, 40, 60))
        plain = BytesIO()
        pixels.save(plain, format="PNG")
        tagged = BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("source", "camera export")
        pixels.save(tagged, format="PNG", pnginfo=metadata)

        self.assertEqual(
            self.service.image_content_hash(plain.getvalue()),
            self.service.image_content_hash(tagged.getvalue()),
        )

    def test_search_skips_vectors_with_a_different_dimension(self):
        self._add_image(10, "https://example.com/invalid.png", [1.0, 0.0, 0.0])

        results = self.service.search_similar_images(
            user_id=10,
            query_vector=[1.0, 0.0],
            top_k=5,
        )

        self.assertEqual([], results)

    def test_text_search_prioritizes_exact_color_in_image_description(self):
        red_key = self._add_image(
            11,
            "https://example.com/red-dress.png",
            [0.8, 0.6],
            description="一位女性穿着红色连衣裙",
            category="outfit",
        )
        self._add_image(
            11,
            "https://example.com/black-dress.png",
            [1.0, 0.0],
            description="一位女性穿着黑色连衣裙",
            category="outfit",
        )

        results = self.service.search_similar_images(
            user_id=11,
            query_vector=[1.0, 0.0],
            top_k=10,
            query_text="红色",
        )

        self.assertEqual([red_key], [item.redisKey for item in results])

    def test_explicit_color_and_item_type_match_can_bypass_score_floor(self):
        red_key = self._add_image(
            17,
            "https://example.com/red-dress-low-score.png",
            [0.1, 0.995],
            description="红色连衣裙",
            category="outfit",
        )
        self._add_image(
            17,
            "https://example.com/black-dress-high-score.png",
            [0.0, 1.0],
            description="黑色连衣裙",
            category="outfit",
        )

        results = self.service.search_similar_images(
            user_id=17,
            query_vector=[1.0, 0.0],
            top_k=10,
            min_score=0.95,
            allowed_categories=["clothing", "outfit"],
            description_keywords=["裙", "裙子", "连衣裙"],
            query_text="红色裙子",
        )

        self.assertEqual([red_key], [item.redisKey for item in results])

    def test_explicit_color_search_does_not_fall_back_to_wrong_color(self):
        self._add_image(
            15,
            "https://example.com/portrait.png",
            [1.0, 0.0],
            description="一位戴着黑框眼镜的女性肖像",
            category="person",
        )

        results = self.service.search_similar_images(
            user_id=15,
            query_vector=[1.0, 0.0],
            top_k=10,
            query_text="红色",
        )

        self.assertEqual([], results)

    def test_search_deduplicates_same_image_hash(self):
        first_key = self._add_image(
            16,
            "https://example.com/copy-a.png",
            [1.0, 0.0],
            description="红色连衣裙",
            image_hash="same-image",
        )
        self._add_image(
            16,
            "https://example.com/copy-b.png",
            [1.0, 0.0],
            description="红色连衣裙",
            image_hash="same-image",
        )

        results = self.service.search_similar_images(
            user_id=16,
            query_vector=[1.0, 0.0],
            top_k=10,
            query_text="红色",
        )

        self.assertEqual(1, len(results))
        self.assertEqual(first_key, results[0].redisKey)

    def test_image_attributes_rerank_matching_color_and_item_type(self):
        blue_key = self._add_image(
            13,
            "https://example.com/blue-dress.png",
            [1.0, 0.0],
            description="蓝色连衣裙",
            category="clothing",
            image_attributes={"category": "clothing", "colors": ["blue"], "itemTypes": ["dress"]},
        )
        black_key = self._add_image(
            13,
            "https://example.com/black-dress.png",
            [0.9, 0.436],
            description="黑色连衣裙",
            category="clothing",
            image_attributes={"category": "clothing", "colors": ["black"], "itemTypes": ["dress"]},
        )

        results = self.service.search_similar_images(
            user_id=13,
            query_vector=[1.0, 0.0],
            top_k=5,
            query_attributes={
                "category": "clothing",
                "colors": ["black"],
                "itemTypes": ["dress"],
            },
        )

        self.assertEqual(black_key, results[0].redisKey)
        self.assertIn(blue_key, [item.redisKey for item in results])

    def test_description_fallback_extracts_color_and_item_type(self):
        attributes = self.service.extract_image_attributes("一件黑色连衣裙")

        self.assertEqual(["black"], attributes["colors"])
        self.assertEqual(["dress"], attributes["itemTypes"])
        self.assertEqual("clothing", attributes["category"])

    def test_structured_image_metadata_response_is_parsed(self):
        description, attributes = self.service.parse_image_metadata_response(
            '{"description":"黑色连衣裙商品图","category":"clothing",'
            '"colors":["black"],"itemTypes":["dress"]}'
        )

        self.assertEqual("黑色连衣裙商品图", description)
        self.assertEqual("clothing", attributes["category"])
        self.assertEqual(["black"], attributes["colors"])
        self.assertEqual(["dress"], attributes["itemTypes"])

    def test_query_image_attributes_are_classified_in_one_batch(self):
        prompts = sum(len(group) for group in self.service.IMAGE_ATTRIBUTE_PROMPTS.values())
        text_vectors = [[0.0, 1.0] for _ in range(prompts)]
        text_vectors[0] = [1.0, 0.0]
        text_vectors[4] = [1.0, 0.0]
        text_vectors[14] = [1.0, 0.0]
        self.service.encode_text_batch = lambda _prompts: text_vectors

        attributes = self.service.infer_query_image_attributes([1.0, 0.0])

        self.assertEqual("clothing", attributes["category"])
        self.assertEqual(["black"], attributes["colors"])
        self.assertEqual(["dress"], attributes["itemTypes"])

    def test_index_saves_clip_vector_when_description_model_fails(self):
        self.service.read_image_data = lambda _url: b"image-bytes"
        self.service.encode_image = lambda _image_data: [0.1, 0.2, 0.3]
        self.service.build_qwen_image_input = lambda _url, _data: "image-input"

        def fail_description(_image_input):
            raise RuntimeError("description model unavailable")

        self.service.describe_image = fail_description
        response = self.service.index_image("https://example.com/image.png", user_id=9)

        index_key = self.service.build_user_index_key(9)
        redis_key = self.service.build_image_key(9, response.ossUrl)
        payload = json.loads(self.service.redis_client.values[redis_key])
        self.assertIn(redis_key, self.service.redis_client.sets[index_key])
        self.assertEqual([0.1, 0.2, 0.3], payload["vector"])
        self.assertEqual("", payload["description"])


if __name__ == "__main__":
    unittest.main()
