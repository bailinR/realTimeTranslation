from __future__ import annotations

import httpx

from app.models import TranslationStyle
from app.net_utils import summarize_httpx_exception


LANGUAGE_NAMES = {
    "auto": "自动检测",
    "en": "英语",
    "th": "泰语",
    "vi": "越南语",
}


class OpenAICompatibleTranslator:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        style: TranslationStyle = TranslationStyle.LIVE_COMMERCE,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.style = style
        self.client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            trust_env=False,
        )

    async def translate(self, text: str, source_lang: str, context: list[str]) -> str:
        if not text.strip():
            return ""
        context_lines = "\n".join(f"- {line}" for line in context[-2:] if line.strip())
        payload = {
            "model": self.model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": self._build_user_prompt(
                        text=text,
                        source_lang=source_lang,
                        context_lines=context_lines or "- 无",
                    ),
                },
            ],
        }
        try:
            response = await self.client.post(f"{self.base_url}/chat/completions", json=payload)
        except httpx.RequestError as exc:
            raise RuntimeError(summarize_httpx_exception(exc)) from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(summarize_httpx_exception(exc)) from exc
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return text
        message = choices[0].get("message") or {}
        return (message.get("content") or text).strip()

    async def aclose(self) -> None:
        await self.client.aclose()

    def _style_block(self) -> str:
        if self.style == TranslationStyle.LIVE_COMMERCE:
            return (
                "【风格：直播带货】保留促销节奏与紧迫感，数字、价格、优惠、库存、链接口令等尽量原样或直译；"
                "口语叫卖感可略作润色但不要改成书面语；品牌名、SKU、人名保留常见写法。"
            )
        if self.style == TranslationStyle.COLLOQUIAL:
            return (
                "【风格：口语】用自然口语化的简体中文字幕，短句优先，像朋友聊天；"
                "避免公文腔和过度书面词，但不要用低俗或过度网络梗。"
            )
        return (
            "【风格：正式】用语规范、清晰，可用适度书面表达，适合新闻、演讲、正式解说；"
            "避免俚语与夸张促销话术，数字与专有名词准确。"
        )

    def _system_prompt(self) -> str:
        base = (
            "你是直播实时字幕翻译助手。"
            "你的任务是把当前这一句翻译成简体中文字幕。"
            "不要补写下一句，不要把上一句合并进来，不要总结，不要解释。"
            "遇到残句、口误、听不清、语义不完整时，宁可保守直译，也不要脑补。"
            "品牌名、人名、地名、商品名优先保留原文或做简短音译。"
            "输出只能是译文本身。"
        )
        return f"{base}\n{self._style_block()}"

    def _build_user_prompt(self, *, text: str, source_lang: str, context_lines: str) -> str:
        language_name = LANGUAGE_NAMES.get(source_lang, source_lang or "自动检测")
        return (
            f"源语言: {language_name}\n"
            f"上文参考:\n{context_lines}\n\n"
            f"当前这一句:\n{text}"
        )
