from __future__ import annotations

import httpx


class OpenAICompatibleTranslator:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )

    async def translate(self, text: str, source_lang: str, context: list[str]) -> str:
        if not text.strip():
            return ""
        context_lines = "\n".join(f"- {line}" for line in context[-2:] if line.strip())
        prompt = (
            "你是直播字幕翻译助手。"
            "请把输入的泰语、越南语或英语自然翻译成简体中文。"
            "保留主播语气，不要扩写。专有名词优先音译，必要时补充简短括注。"
        )
        user_text = f"源语言: {source_lang}\n上下文:\n{context_lines or '- 无'}\n\n原文:\n{text}"
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_text},
            ],
        }
        response = await self.client.post(f"{self.base_url}/chat/completions", json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response is not None else ""
            raise RuntimeError(f"{exc} {body}".strip()) from exc
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return text
        message = choices[0].get("message") or {}
        return (message.get("content") or text).strip()

    async def aclose(self) -> None:
        await self.client.aclose()
