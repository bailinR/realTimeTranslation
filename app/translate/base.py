from __future__ import annotations

from typing import Protocol


class TranslationProvider(Protocol):
    async def translate(self, text: str, source_lang: str, context: list[str]) -> str: ...
