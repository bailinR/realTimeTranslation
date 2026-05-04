from __future__ import annotations

from app.models import AudioChunk, RecognitionMode


class ChunkScheduler:
    def __init__(self, sample_rate: int, mode: RecognitionMode, *, step_ms: int | None = None, window_ms: int | None = None) -> None:
        self.sample_rate = sample_rate
        self.mode = mode
        self._pcm = bytearray()
        self._next_chunk_id = 1
        self._step_ms = step_ms or (3200 if mode == RecognitionMode.PRECISE else 1400)
        self._window_ms = window_ms or (3800 if mode == RecognitionMode.PRECISE else 2200)
        self._last_emit_end_ms = 0
        self._total_ms = 0

    def push(self, mono_pcm: bytes) -> list[AudioChunk]:
        if not mono_pcm:
            return []
        self._pcm.extend(mono_pcm)
        self._total_ms += int(len(mono_pcm) / 2 / self.sample_rate * 1000)
        chunks: list[AudioChunk] = []
        while self._total_ms - self._last_emit_end_ms >= self._step_ms:
            end_ms = self._last_emit_end_ms + self._step_ms
            start_ms = max(0, end_ms - self._window_ms)
            start_index = int(start_ms * self.sample_rate / 1000) * 2
            end_index = int(end_ms * self.sample_rate / 1000) * 2
            payload = bytes(self._pcm[start_index:end_index])
            chunks.append(
                AudioChunk(
                    chunk_id=self._next_chunk_id,
                    pcm_bytes=payload,
                    sample_rate=self.sample_rate,
                    channels=1,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
            )
            self._next_chunk_id += 1
            self._last_emit_end_ms = end_ms
        self._trim()
        return chunks

    def _trim(self) -> None:
        keep_ms = max(self._window_ms * 2, 10_000)
        if self._total_ms <= keep_ms:
            return
        trim_ms = self._total_ms - keep_ms
        trim_bytes = int(trim_ms * self.sample_rate / 1000) * 2
        del self._pcm[:trim_bytes]
        self._total_ms -= trim_ms
        self._last_emit_end_ms = max(0, self._last_emit_end_ms - trim_ms)
