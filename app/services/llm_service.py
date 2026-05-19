import json
import os
from collections.abc import Iterator

import requests
from dotenv import load_dotenv

from app.core.config import settings


load_dotenv()


class LLMService:
    """负责调用外部 LLM，或者在失败时回退到本地结果。"""

    def __init__(self) -> None:
        """从环境变量中读取模型调用所需配置。"""
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    def generate_recommendation(self, prompt: str, fallback_data: dict) -> tuple[dict, str]:
        """优先调用真实模型；如果缺少配置或调用失败，就返回 fallback 结果。"""
        if not self.api_key:
            return fallback_data, "fallback"

        try:
            return self._call_openai_compatible_api(prompt), self.model
        except Exception:
            return fallback_data, "fallback"

    def generate_chat_answer(self, message: str, context: str, history: str = "") -> tuple[str, str]:
        """根据 RAG 检索到的知识片段生成自然语言回答。"""
        fallback_answer = self._build_rag_fallback_answer(message, context)

        if settings.dashscope_api_key:
            try:
                return self._call_tongyi_chat(message, context, history), "qwen"
            except Exception:
                pass

        if self.api_key:
            try:
                return self._call_openai_chat(message, context, history), self.model
            except Exception:
                pass

        return fallback_answer, "fallback"

    def stream_chat_answer(self, message: str, context: str, history: str = "") -> Iterator[tuple[str, str]]:
        """流式生成 RAG 回答，每次产出一小段文本和模型来源。"""
        if settings.dashscope_api_key:
            try:
                yield from self._stream_tongyi_chat(message, context, history)
                return
            except Exception:
                pass

        if self.api_key:
            try:
                yield from self._stream_openai_chat(message, context, history)
                return
            except Exception:
                pass

        fallback_answer = self._build_rag_fallback_answer(message, context)
        for chunk in self._split_text_for_stream(fallback_answer):
            yield chunk, "fallback"

    def _stream_tongyi_chat(self, message: str, context: str, history: str = "") -> Iterator[tuple[str, str]]:
        """调用通义千问流式接口，让前端可以边生成边显示。"""
        from dashscope import Generation

        responses = Generation.call(
            model=os.getenv("DASHSCOPE_TEXT_MODEL", "qwen-plus"),
            api_key=settings.dashscope_api_key,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 AIWear 的穿搭顾问。只能基于给定知识库和用户问题回答，"
                        "回答要中文、具体、适合普通用户阅读。"
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_rag_prompt(message, context, history),
                },
            ],
            result_format="message",
            stream=True,
            incremental_output=True,
            temperature=0.3,
        )

        for response in responses:
            text = self.extract_dashscope_text(response)
            if text:
                yield text, "qwen"

    @staticmethod
    def extract_dashscope_text(response) -> str:
        """从 DashScope 流式响应里提取本次增量文本。

        DashScope SDK 返回对象有时像字典，有时是带属性的对象，所以这里两种方式都兼容。
        """
        if hasattr(response, "output"):
            output = response.output
        else:
            output = response.get("output", {}) if isinstance(response, dict) else {}

        if isinstance(output, dict):
            text = output.get("text")
            if text:
                return str(text)
            choices = output.get("choices") or []
        else:
            text = getattr(output, "text", "")
            if text:
                return str(text)
            choices = getattr(output, "choices", []) or []

        if not choices:
            return ""

        choice = choices[0]
        if isinstance(choice, dict):
            message = choice.get("message", {})
            content = message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")
        else:
            message = getattr(choice, "message", None)
            content = getattr(message, "content", "") if message is not None else ""

        return str(content or "")

    def _stream_openai_chat(self, message: str, context: str, history: str = "") -> Iterator[tuple[str, str]]:
        """调用 OpenAI 兼容接口的流式返回。"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0.3,
            "stream": True,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 AIWear 的穿搭顾问。只能基于给定知识库和用户问题回答，"
                        "回答要中文、具体、适合普通用户阅读。"
                    ),
                },
                {"role": "user", "content": self._build_rag_prompt(message, context, history)},
            ],
        }

        with requests.post(url, headers=headers, json=payload, timeout=60, stream=True) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data:"):
                    continue
                line = raw_line.removeprefix("data:").strip()
                if line == "[DONE]":
                    break
                data = json.loads(line)
                text = data["choices"][0].get("delta", {}).get("content", "")
                if text:
                    yield text, self.model

    def _split_text_for_stream(self, text: str, size: int = 8) -> Iterator[str]:
        """把 fallback 文本切成小块，保证无模型时前端也有一致的流式体验。"""
        for index in range(0, len(text), size):
            yield text[index : index + size]

    def _call_tongyi_chat(self, message: str, context: str, history: str = "") -> str:
        """调用通义文本模型生成 RAG 回答。"""
        from langchain_community.chat_models.tongyi import ChatTongyi
        from langchain_core.messages import HumanMessage, SystemMessage

        model = ChatTongyi(
            model_name=os.getenv("DASHSCOPE_TEXT_MODEL", "qwen-turbo"),
            temperature=0.3,
            dashscope_api_key=settings.dashscope_api_key,
        )
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "你是 AIWear 的穿搭顾问。只能基于给定知识库和用户问题回答，"
                        "回答要中文、具体、适合普通用户阅读。"
                    )
                ),
                HumanMessage(content=self._build_rag_prompt(message, context, history)),
            ]
        )
        return str(response.content).strip()

    def _call_openai_chat(self, message: str, context: str, history: str = "") -> str:
        """调用 OpenAI 兼容接口生成 RAG 回答。"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 AIWear 的穿搭顾问。只能基于给定知识库和用户问题回答，"
                        "回答要中文、具体、适合普通用户阅读。"
                    ),
                },
                {"role": "user", "content": self._build_rag_prompt(message, context, history)},
            ],
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"]).strip()

    def _build_rag_prompt(self, message: str, context: str, history: str = "") -> str:
        """组装 RAG 提示词。"""
        history_text = history.strip() or "无"
        return (
            "[最近对话]\n"
            f"{history_text}\n\n"
            "[知识库片段]\n"
            f"{context}\n\n"
            "[用户问题]\n"
            f"{message}\n\n"
            "[回答要求]\n"
            "1. 先给出总体建议。\n"
            "2. 再给出 3 到 5 条具体搭配建议。\n"
            "3. 最后给出需要避免的穿搭问题。\n"
            "4. 不要推荐具体品牌。"
        )

    def _build_rag_fallback_answer(self, message: str, context: str) -> str:
        """模型不可用时，根据命中的知识片段给出最小可用回答。"""
        first_context = context.strip().split("\n\n")[0] if context.strip() else ""
        if first_context:
            return (
                f"针对“{message}”，可以参考知识库中的相关建议：\n"
                f"{first_context}\n\n"
                "整体上建议优先选择合身、干净、场景匹配的搭配，避免颜色过多或版型过紧。"
            )
        return (
            f"针对“{message}”，建议先明确场景、身材特点和喜欢的风格，"
            "再选择颜色协调、版型合身、舒适度足够的单品组合。"
        )

    def _call_openai_compatible_api(self, prompt: str) -> dict:
        """按照 OpenAI 兼容接口格式发起请求，并解析返回的 JSON 内容。"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a fashion assistant. "
                        "Return valid JSON with keys: "
                        "summary, outfit_items, reasons, alternatives, avoid_tips."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        return {
            "summary": parsed.get("summary", ""),
            "outfit_items": parsed.get("outfit_items", []),
            "reasons": parsed.get("reasons", []),
            "alternatives": parsed.get("alternatives", []),
            "avoid_tips": parsed.get("avoid_tips", []),
        }
