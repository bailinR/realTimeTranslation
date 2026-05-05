from __future__ import annotations

import asyncio
import base64
import io
import logging
import wave
from collections.abc import Awaitable, Callable

import httpx

from app.models import AudioChunk, ProviderError, TranscriptResult
from app.net_utils import summarize_httpx_exception


class OpenAIChunkTranscriptionProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        language: str,
        timeout_seconds: float,
        on_result: Callable[[TranscriptResult], Awaitable[None]],
        on_error: Callable[[ProviderError], Awaitable[None]],
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.language = language
        self.timeout_seconds = timeout_seconds
        self.on_result = on_result
        self.on_error = on_error
        self.logger = logging.getLogger(__name__)
        self.client: httpx.AsyncClient | None = None
        self.queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue()
        self.worker: asyncio.Task | None = None

    def _http_timeout(self) -> httpx.Timeout:
        # DashScope ASR over chat/completions can block on read long after upload; a single
        # float applies to every phase and was too short for slow responses → ReadTimeout.
        t = float(self.timeout_seconds)
        read_s = min(240.0, max(90.0, t * 3.0))
        return httpx.Timeout(connect=20.0, read=read_s, write=max(30.0, t), pool=15.0)

    async def start(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=self._http_timeout(),
            headers={"Authorization": f"Bearer {self.api_key}"},
            trust_env=False,
        )
        self.worker = asyncio.create_task(self._run())

    async def push_audio(self, chunk: AudioChunk) -> None:
        await self.queue.put(chunk)

    async def stop(self) -> None:
        await self.queue.put(None)
        if self.worker:
            await self.worker
        if self.client:
            await self.client.aclose()

    async def _run(self) -> None:
        while True:
            chunk = await self.queue.get()
            if chunk is None:
                break
            try:
                if not self.client:
                    raise RuntimeError("HTTP client is not started")
                response = await self._post_transcription_with_retry(chunk)
                response.raise_for_status()
                payload = response.json()
                text, language = self._extract_transcript(payload)
                if text:
                    await self.on_result(
                        TranscriptResult(
                            chunk_id=chunk.chunk_id,
                            start_ms=chunk.start_ms,
                            end_ms=chunk.end_ms,
                            text=text,
                            source_lang=language,
                            provider="cloud",
                            is_final=True,
                        )
                    )
            except httpx.HTTPStatusError as exc:
                message = summarize_httpx_exception(exc)
                await self.on_error(
                    ProviderError(provider="cloud", code="transcription-failed", message=message, recoverable=True)
                )
            except httpx.RequestError as exc:
                message = summarize_httpx_exception(exc)
                await self.on_error(
                    ProviderError(provider="cloud", code="transcription-failed", message=message, recoverable=True)
                )
            except Exception as exc:
                self.logger.exception("Unexpected cloud transcription failure")
                await self.on_error(
                    ProviderError(
                        provider="cloud",
                        code="transcription-failed",
                        message=summarize_httpx_exception(exc),
                        recoverable=True,
                    )
                )

    async def _post_transcription_with_retry(self, chunk: AudioChunk) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                return await self._post_transcription(chunk)
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                if attempt == 0:
                    self.logger.warning("Cloud transcription request failed (%s), retrying once", type(exc).__name__)
                    await asyncio.sleep(1.5)
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    async def _post_transcription(self, chunk: AudioChunk) -> httpx.Response:
        if not self.client:
            raise RuntimeError("HTTP client is not started")
        if self._use_dashscope_asr_compat():
            return await self.client.post(
                f"{self.base_url}/chat/completions",
                json=self._build_dashscope_payload(chunk),
            )
        wav_bytes = _pcm_to_wav_bytes(chunk.pcm_bytes, chunk.sample_rate)
        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        data = {"model": self.model, "response_format": "verbose_json"}
        if self.language != "auto":
            data["language"] = self.language
        return await self.client.post(f"{self.base_url}/audio/transcriptions", data=data, files=files)

    def _use_dashscope_asr_compat(self) -> bool:
        host = self.base_url.lower()
        return "dashscope.aliyuncs.com/compatible-mode" in host and self.model.startswith("qwen3-asr-")

    def _build_dashscope_payload(self, chunk: AudioChunk) -> dict:
        wav_bytes = _pcm_to_wav_bytes(chunk.pcm_bytes, chunk.sample_rate)
        data_uri = "data:audio/wav;base64," + base64.b64encode(wav_bytes).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": data_uri,
                            },
                        }
                    ],
                }
            ],
            "stream": False,
            "asr_options": {
                "enable_itn": False,
            },
        }
        if self.language != "auto":
            payload["asr_options"]["language"] = self.language
        return payload

    def _extract_transcript(self, payload: dict) -> tuple[str, str]:
        if "text" in payload:
            return (payload.get("text") or "").strip(), payload.get("language") or self.language or "auto"

        choices = payload.get("choices") or []
        if not choices:
            return "", self.language or "auto"
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        text = self._content_to_text(content).strip()
        annotations = message.get("annotations") or []
        language = self.language or "auto"
        for item in annotations:
            if item.get("type") == "audio_info" and item.get("language"):
                language = item["language"]
                break
        return text, language

    def _content_to_text(self, content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content") or ""
                    if text:
                        parts.append(str(text))
                elif isinstance(item, str):
                    parts.append(item)
            return "".join(parts)
        return str(content or "")


def _pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()
