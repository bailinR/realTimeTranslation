from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.models import AudioChunk, ProviderError, TranscriptResult


ResultCallback = Callable[[TranscriptResult], Awaitable[None]]
ErrorCallback = Callable[[ProviderError], Awaitable[None]]


class TranscriptionProvider(Protocol):
    async def start(self) -> None: ...
    async def push_audio(self, chunk: AudioChunk) -> None: ...
    async def stop(self) -> None: ...
