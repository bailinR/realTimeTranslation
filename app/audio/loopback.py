from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

import pyaudiowpatch as pyaudio

from app.models import AudioSourceConfig, ProviderError


AudioCallback = Callable[[bytes, int, int], None]
ErrorCallback = Callable[[ProviderError], None]


class LoopbackAudioSource:
    def __init__(self, config: AudioSourceConfig, on_audio: AudioCallback, on_error: ErrorCallback) -> None:
        self.config = config
        self.on_audio = on_audio
        self.on_error = on_error
        self.logger = logging.getLogger(__name__)
        self._audio = pyaudio.PyAudio()
        self._stream = None
        self._monitor_task: asyncio.Task | None = None
        self._running = False
        self._device_index: int | None = None
        self.device_name: str = ""
        self.sample_rate = 48_000
        self.channels = 2

    def _default_loopback_info(self) -> dict:
        try:
            if hasattr(self._audio, "get_default_wasapi_loopback"):
                return self._audio.get_default_wasapi_loopback()
            if hasattr(self._audio, "get_default_output_device_info") and hasattr(self._audio, "get_wasapi_loopback_analogue_by_index"):
                default_output = self._audio.get_default_output_device_info()
                return self._audio.get_wasapi_loopback_analogue_by_index(default_output["index"])
            if hasattr(self._audio, "get_loopback_device_info_generator"):
                return next(self._audio.get_loopback_device_info_generator())
        except Exception as exc:
            raise RuntimeError("Unable to locate WASAPI loopback device") from exc
        raise RuntimeError("Unable to locate WASAPI loopback device")

    async def start(self) -> None:
        self._running = True
        await self._open_stream()
        self._monitor_task = asyncio.create_task(self._monitor_default_device())

    async def stop(self) -> None:
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        self._audio.terminate()

    async def _open_stream(self) -> None:
        info = self._default_loopback_info() if self.config.follow_default_output or self.config.device_index is None else self._audio.get_device_info_by_index(self.config.device_index)
        self._device_index = int(info["index"])
        self.device_name = str(info.get("name", f"device-{self._device_index}"))
        self.sample_rate = int(info["defaultSampleRate"])
        self.channels = max(1, min(2, int(info["maxInputChannels"])))
        self.logger.info(
            "Opening loopback device index=%s name=%s sample_rate=%s channels=%s",
            self._device_index,
            self.device_name,
            self.sample_rate,
            self.channels,
        )

        def callback(in_data, frame_count, time_info, status):
            try:
                if status:
                    self.on_error(ProviderError(provider="audio", code="stream-status", message=f"Audio callback status={status}"))
                if in_data:
                    self.on_audio(in_data, self.sample_rate, self.channels)
            except Exception as exc:
                self.on_error(ProviderError(provider="audio", code="callback-failed", message=str(exc)))
            return (None, pyaudio.paContinue)

        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.config.frames_per_buffer,
            input_device_index=self._device_index,
            stream_callback=callback,
        )
        self._stream.start_stream()

    async def _monitor_default_device(self) -> None:
        while self._running:
            await asyncio.sleep(2)
            if not self.config.follow_default_output:
                continue
            try:
                info = self._default_loopback_info()
                current = int(info["index"])
                if current != self._device_index:
                    self.logger.info("Default output changed from %s to %s; restarting loopback", self._device_index, current)
                    if self._stream:
                        self._stream.stop_stream()
                        self._stream.close()
                    await self._open_stream()
            except Exception as exc:
                self.on_error(ProviderError(provider="audio", code="device-monitor", message=str(exc)))
