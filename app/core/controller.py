from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, Signal

from app.asr.cloud_openai import OpenAIChunkTranscriptionProvider
from app.asr.local_faster_whisper import FasterWhisperProvider
from app.audio.loopback import LoopbackAudioSource
from app.audio.processing import downmix_to_mono
from app.config import AppPaths
from app.core.chunking import ChunkScheduler
from app.core.events import EventBus
from app.core.language import LanguageLock
from app.core.text_utils import compact_whitespace, remove_adjacent_overlap, remove_overlap
from app.models import AppSettings, ProviderError, RecognitionMode, SubtitleSegment, SubtitleStatus, TranscriptResult
from app.store.database import Database
from app.store.settings_secrets import SecretStore
from app.translate.openai_compatible import OpenAICompatibleTranslator


class AppController(QObject):
    segment_updated = Signal(object)
    session_changed = Signal(object)
    running_changed = Signal(bool)
    status_changed = Signal(str)
    error_occurred = Signal(object)
    overlay_updated = Signal(str, str)
    diagnostic_logged = Signal(str, str)

    def __init__(self, settings: AppSettings, paths: AppPaths, db: Database, secrets: SecretStore, bus: EventBus) -> None:
        super().__init__()
        self.settings = settings
        self.paths = paths
        self.db = db
        self.secrets = secrets
        self.bus = bus
        self.logger = logging.getLogger(__name__)
        self.session_id: int | None = None
        self.audio_source: LoopbackAudioSource | None = None
        self.cloud_provider: OpenAIChunkTranscriptionProvider | None = None
        self.local_provider: FasterWhisperProvider | None = None
        self.translator: OpenAICompatibleTranslator | None = None
        self.scheduler: ChunkScheduler | None = None
        self.language_lock = LanguageLock(settings.recognition.source_language)
        self.segments_by_chunk: dict[int, SubtitleSegment] = {}
        self.final_source_history: list[str] = []
        self.final_translation_history: list[str] = []
        self.last_final_source_text = ""
        self.cloud_failures = 0
        self.degraded_local_only = False
        self._lock = asyncio.Lock()
        self.session_started_at: datetime | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.audio_packets_received = 0
        self.chunks_dispatched = 0
        self._health_task: asyncio.Task | None = None
        self._warned_no_audio = False

    async def start(self) -> None:
        if self.session_id is not None:
            return
        try:
            self.loop = asyncio.get_running_loop()
            self.audio_packets_received = 0
            self.chunks_dispatched = 0
            self._warned_no_audio = False
            self.session_started_at = datetime.now()

            api_key = self.secrets.get(self.settings.transcribe_api_key_name)
            translate_key = self.secrets.get(self.settings.translate_api_key_name)
            if not api_key:
                await self._handle_error(
                    ProviderError(provider="config", code="missing-transcribe-key", message="缺少转写 API Key，请先打开设置填写。", recoverable=False)
                )
                return
            if not translate_key:
                self._log("warning", "未单独填写翻译 API Key，当前复用转写 API Key。")

            self.session_id = self.db.create_session(
                mode=self.settings.recognition.mode.value,
                source_language=self.settings.recognition.source_language,
            )
            self.language_lock = LanguageLock(self.settings.recognition.source_language)
            self.session_changed.emit(self.db.list_sessions())

            self.translator = OpenAICompatibleTranslator(
                base_url=self.settings.recognition.base_url,
                api_key=translate_key or api_key,
                model=self.settings.recognition.translate_model,
                timeout_seconds=self.settings.recognition.timeout_seconds,
                style=self.settings.recognition.translation_style,
            )
            self.cloud_provider = OpenAIChunkTranscriptionProvider(
                base_url=self.settings.recognition.base_url,
                api_key=api_key,
                model=self.settings.recognition.transcribe_model,
                language=self.settings.recognition.source_language,
                timeout_seconds=self.settings.recognition.timeout_seconds,
                on_result=self._handle_transcript,
                on_error=self._handle_error,
            )
            self.local_provider = FasterWhisperProvider(
                model_size=self.settings.recognition.local_model_size,
                compute_type=self.settings.local_compute_type,
                language=self.settings.recognition.source_language,
                on_result=self._handle_transcript,
                on_error=self._handle_error,
            )
            self.audio_source = LoopbackAudioSource(self.settings.audio, self._handle_audio, self._handle_sync_error)

            await self.cloud_provider.start()
            if self.settings.recognition.mode == RecognitionMode.REALTIME:
                await self.local_provider.start()

            self.status_changed.emit("正在采集系统声音...")
            self._log(
                "info",
                f"会话已启动，模式={self.settings.recognition.mode.value}，语言={self.settings.recognition.source_language}，转写模型={self.settings.recognition.transcribe_model}，翻译模型={self.settings.recognition.translate_model}",
            )
            await self.audio_source.start()
            self._log("info", f"已打开回环设备：{self.audio_source.device_name}")
            self.running_changed.emit(True)
            self._health_task = asyncio.create_task(self._health_monitor())
        except Exception as exc:
            await self._handle_error(
                ProviderError(provider="startup", code="start-failed", message=str(exc), recoverable=False)
            )
            await self.stop()

    async def stop(self) -> None:
        if self.session_id is None:
            return
        if self._health_task:
            self._health_task.cancel()
            self._health_task = None
        if self.audio_source:
            await self.audio_source.stop()
        if self.cloud_provider:
            await self.cloud_provider.stop()
        if self.local_provider:
            await self.local_provider.stop()
        if self.translator:
            await self.translator.aclose()
        self.db.end_session(self.session_id)
        self.session_changed.emit(self.db.list_sessions())
        self.status_changed.emit("已停止")
        self.session_id = None
        self.scheduler = None
        self.segments_by_chunk.clear()
        self.final_source_history.clear()
        self.final_translation_history.clear()
        self.last_final_source_text = ""
        self.session_started_at = None
        self.language_lock = LanguageLock(self.settings.recognition.source_language)
        self.running_changed.emit(False)
        self._log("info", "会话已停止。")

    async def recover_cloud(self) -> None:
        self.cloud_failures = 0
        self.degraded_local_only = False
        self.status_changed.emit("已恢复混合模式")
        self._log("info", "已手动恢复云端识别。")

    def _handle_audio(self, pcm_bytes: bytes, sample_rate: int, channels: int) -> None:
        if not self.loop:
            return
        self.loop.call_soon_threadsafe(self._process_audio_frame, pcm_bytes, sample_rate, channels)

    def _process_audio_frame(self, pcm_bytes: bytes, sample_rate: int, channels: int) -> None:
        mono = downmix_to_mono(pcm_bytes, channels)
        self.audio_packets_received += 1
        if self.audio_packets_received == 1:
            self.status_changed.emit("已接收到系统声音，正在分块识别...")
            self._log("info", f"已接收到第一帧系统声音，采样率={sample_rate}Hz，声道={channels}")
        if self.scheduler is None or self.scheduler.sample_rate != sample_rate:
            if self.settings.recognition.mode == RecognitionMode.PRECISE:
                self.scheduler = ChunkScheduler(
                    sample_rate,
                    self.settings.recognition.mode,
                    step_ms=self.settings.recognition.cloud_step_ms_steady,
                    window_ms=self.settings.recognition.cloud_chunk_ms_steady,
                )
            else:
                self.scheduler = ChunkScheduler(
                    sample_rate,
                    self.settings.recognition.mode,
                    step_ms=self.settings.recognition.step_ms_fast,
                    window_ms=self.settings.recognition.chunk_ms_fast,
                )
            self._log("info", f"已初始化分块器，step={self.scheduler._step_ms}ms，window={self.scheduler._window_ms}ms")
        chunks = self.scheduler.push(mono)
        for chunk in chunks:
            self.chunks_dispatched += 1
            if self.chunks_dispatched == 1:
                self._log("info", "已生成首个识别音频分块，开始送往识别 provider。")
            asyncio.create_task(self._dispatch_chunk(chunk))

    async def _dispatch_chunk(self, chunk) -> None:
        try:
            if self.settings.recognition.mode == RecognitionMode.REALTIME and self.local_provider:
                await self.local_provider.push_audio(chunk)
            if self.cloud_provider and not self.degraded_local_only:
                await self.cloud_provider.push_audio(chunk)
        except Exception as exc:
            await self._handle_error(
                ProviderError(provider="pipeline", code="dispatch-failed", message=str(exc), recoverable=True)
            )

    async def _handle_transcript(self, result: TranscriptResult) -> None:
        async with self._lock:
            if self.session_id is None:
                return
            text = compact_whitespace(result.text)
            previous = self.segments_by_chunk.get(result.chunk_id)
            if previous:
                text = remove_overlap(previous.source_text, text)
            elif result.is_final and self.last_final_source_text:
                text = remove_adjacent_overlap(self.last_final_source_text, text)
            if not text:
                return
            locked = self.language_lock.observe(result.source_lang)
            effective_lang = locked or result.source_lang or "auto"
            translated = await self._translate(text, effective_lang)
            status = SubtitleStatus.FINAL if result.is_final else SubtitleStatus.DRAFT
            session_started_at = self.session_started_at or datetime.now()
            segment = SubtitleSegment(
                seq=0,
                session_id=self.session_id,
                chunk_id=result.chunk_id,
                started_at=session_started_at + timedelta(milliseconds=result.start_ms),
                ended_at=session_started_at + timedelta(milliseconds=result.end_ms),
                source_lang=effective_lang,
                source_text=text,
                translated_text=translated,
                status=status,
                provider=result.provider,
            )
            if previous and previous.status == SubtitleStatus.DRAFT and status == SubtitleStatus.FINAL:
                segment.source_text = remove_overlap(previous.source_text, segment.source_text) or segment.source_text
            self.db.upsert_segment(segment)
            self.segments_by_chunk[result.chunk_id] = segment
            self.segment_updated.emit(segment)

            if result.provider == "cloud":
                self.cloud_failures = 0
                if status == SubtitleStatus.FINAL:
                    self.last_final_source_text = segment.source_text
                    self.final_source_history.append(segment.source_text)
                    self.final_translation_history.append(segment.translated_text)
                    self.final_source_history = self.final_source_history[-5:]
                    self.final_translation_history = self.final_translation_history[-5:]
            self._update_overlay(segment)
            if status == SubtitleStatus.FINAL:
                self.status_changed.emit("实时翻译中")
                self._log("info", f"收到最终转写并完成翻译，chunk={result.chunk_id}，语言={effective_lang}，provider={result.provider}")

    async def _translate(self, text: str, source_lang: str) -> str:
        if not self.translator:
            return text
        context = self.final_source_history[-2:] + self.final_translation_history[-2:]
        try:
            return await self.translator.translate(text, source_lang, context)
        except Exception as exc:
            await self._handle_error(
                ProviderError(provider="translator", code="translate-failed", message=str(exc), recoverable=True)
            )
            return text

    async def _handle_error(self, error: ProviderError) -> None:
        self.error_occurred.emit(error)
        self._log("error", f"{error.provider}/{error.code}: {error.message}")
        if error.provider == "cloud":
            self.cloud_failures += 1
            if self.cloud_failures >= self.settings.recognition.cloud_fail_threshold:
                self.degraded_local_only = True
                self.status_changed.emit("云端不可用，已降级到本地模式")
            else:
                self.status_changed.emit(f"云端识别失败（{self.cloud_failures}/{self.settings.recognition.cloud_fail_threshold}）")
        else:
            self.status_changed.emit(error.message)

    def _handle_sync_error(self, error: ProviderError) -> None:
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._handle_error(error), self.loop)

    def _update_overlay(self, segment: SubtitleSegment) -> None:
        self.overlay_updated.emit(segment.source_text, segment.translated_text)

    async def _health_monitor(self) -> None:
        while self.session_id is not None:
            await asyncio.sleep(3)
            if self.session_started_at is None:
                continue
            elapsed = (datetime.now() - self.session_started_at).total_seconds()
            if self.audio_packets_received == 0 and elapsed >= 5 and not self._warned_no_audio:
                self._warned_no_audio = True
                message = "已开始采集，但 5 秒内没有收到系统播放声音。请确认直播正在播放，且声音走当前默认输出设备。"
                self.status_changed.emit(message)
                self._log("warning", message)
            elif self.audio_packets_received > 0 and self.chunks_dispatched == 0 and elapsed >= 5:
                self._log("warning", "已收到音频帧，但还没生成识别分块，请检查分块参数或音频是否持续输出。")

    def _log(self, level: str, message: str) -> None:
        self.logger.info("[%s] %s", level.upper(), message)
        self.diagnostic_logged.emit(level, message)
