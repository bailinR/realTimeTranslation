from __future__ import annotations

import asyncio
import os
import tempfile
import wave
from collections.abc import Awaitable, Callable

from app.models import AudioChunk, ProviderError, TranscriptResult

try:
    from faster_whisper import WhisperModel
except ImportError:  # pragma: no cover
    WhisperModel = None


class FasterWhisperProvider:
    def __init__(
        self,
        *,
        model_size: str,
        compute_type: str,
        language: str,
        on_result: Callable[[TranscriptResult], Awaitable[None]],
        on_error: Callable[[ProviderError], Awaitable[None]],
    ) -> None:
        self.model_size = model_size
        self.compute_type = compute_type
        self.language = language
        self.on_result = on_result
        self.on_error = on_error
        self.model = None
        self.queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue()
        self.worker: asyncio.Task | None = None

    async def start(self) -> None:
        if WhisperModel is None:
            await self.on_error(
                ProviderError(provider="local", code="missing-dependency", message="faster-whisper is not installed")
            )
            return
        self.model = await asyncio.to_thread(WhisperModel, self.model_size, device="cpu", compute_type=self.compute_type)
        self.worker = asyncio.create_task(self._run())

    async def push_audio(self, chunk: AudioChunk) -> None:
        if self.model is not None:
            await self.queue.put(chunk)

    async def stop(self) -> None:
        if self.worker:
            await self.queue.put(None)
            await self.worker

    async def _run(self) -> None:
        while True:
            chunk = await self.queue.get()
            if chunk is None:
                break
            try:
                result = await asyncio.to_thread(self._transcribe_file, chunk)
                if result:
                    await self.on_result(result)
            except Exception as exc:
                await self.on_error(ProviderError(provider="local", code="transcription-failed", message=str(exc)))

    def _transcribe_file(self, chunk: AudioChunk) -> TranscriptResult | None:
        if self.model is None:
            return None
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            with wave.open(path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(chunk.sample_rate)
                wav_file.writeframes(chunk.pcm_bytes)
            segments, info = self.model.transcribe(
                path,
                beam_size=1,
                vad_filter=True,
                language=None if self.language == "auto" else self.language,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            if not text:
                return None
            return TranscriptResult(
                chunk_id=chunk.chunk_id,
                start_ms=chunk.start_ms,
                end_ms=chunk.end_ms,
                text=text,
                source_lang=getattr(info, "language", self.language or "auto"),
                provider="local",
                is_final=False,
            )
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
