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
from app.config import DEFAULT_TRANSCRIBE_API_KEY
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
        self._run_generation = 0
        self._active_transcribe_key_tail = ""
        self._active_translate_key_tail = ""
        self._paused = False

    @property
    def pipeline_running(self) -> bool:
        return self.session_id is not None and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._paused

    async def start(self) -> None:
        if self.session_id is not None:
            if self._paused:
                await self._resume()
            return
        try:
            self._run_generation += 1
            self.loop = asyncio.get_running_loop()
            self.audio_packets_received = 0
            self.chunks_dispatched = 0
            self._warned_no_audio = False
            self.session_started_at = datetime.now()
            self._paused = False

            api_key, effective_translate_key = self._resolve_api_keys()
            if not api_key:
                await self._handle_error(
                    ProviderError(provider="config", code="missing-transcribe-key", message="缺少转写 API Key，请先打开设置填写。", recoverable=False)
                )
                return

            self.session_id = self.db.create_session(
                mode=self.settings.recognition.mode.value,
                source_language=self.settings.recognition.source_language,
            )
            self.language_lock = LanguageLock(self.settings.recognition.source_language)
            self.session_changed.emit((self.db.list_sessions(), self.session_id, True))

            await self._start_pipeline(api_key, effective_translate_key, log_session_start=True)
        except Exception as exc:
            await self._handle_error(
                ProviderError(provider="startup", code="start-failed", message=str(exc), recoverable=False)
            )
            await self.stop()

    def _resolve_api_keys(self) -> tuple[str, str]:
        api_key = self.secrets.get(self.settings.transcribe_api_key_name) or DEFAULT_TRANSCRIBE_API_KEY
        translate_key = self.secrets.get(self.settings.translate_api_key_name)
        share_translate = self.settings.recognition.translate_shares_transcribe_key
        effective_translate_key = api_key if share_translate else (translate_key or api_key)
        self._active_transcribe_key_tail = self._key_tail(api_key)
        self._active_translate_key_tail = self._key_tail(effective_translate_key)
        if api_key:
            if share_translate:
                self._log(
                    "info",
                    "已启用「翻译与转写共用 Key」：请求翻译接口时使用转写 Key"
                    + ("（凭据中仍保留单独翻译 Key）。" if translate_key else "。"),
                )
            elif not translate_key:
                self._log("warning", "未单独填写翻译 API Key，当前复用转写 API Key。")
        return api_key, effective_translate_key

    async def _start_pipeline(self, api_key: str, effective_translate_key: str, *, log_session_start: bool) -> None:
        self.translator = OpenAICompatibleTranslator(
            base_url=self.settings.recognition.translate_base_url,
            api_key=effective_translate_key,
            model=self.settings.recognition.translate_model,
            timeout_seconds=self.settings.recognition.timeout_seconds,
            style=self.settings.recognition.translation_style,
            recognition_mode=self.settings.recognition.mode,
            translation_domain=self.settings.recognition.translation_domain,
            glossary_text=self.settings.recognition.translation_glossary,
            names_text=self.settings.recognition.translation_names,
        )
        self.cloud_provider = OpenAIChunkTranscriptionProvider(
            base_url=self.settings.recognition.transcribe_base_url,
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
        if log_session_start:
            self._log(
                "info",
                f"会话已启动，模式={self.settings.recognition.mode.value}，语言={self.settings.recognition.source_language}，转写模型={self.settings.recognition.transcribe_model}，翻译模型={self.settings.recognition.translate_model}",
            )
        else:
            self._log("info", "已继续当前会话的翻译采集。")
        self._log("info", f"转写配置: {self._provider_context('cloud')}")
        self._log("info", f"翻译配置: {self._provider_context('translator')}")
        await self.audio_source.start()
        self._log("info", f"已打开回环设备：{self.audio_source.device_name}")
        self.running_changed.emit(True)
        self._health_task = asyncio.create_task(self._health_monitor())

    async def pause(self) -> None:
        if self.session_id is None or self._paused:
            return
        self._run_generation += 1
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
        self.audio_source = None
        self.cloud_provider = None
        self.local_provider = None
        self.translator = None
        self.scheduler = None
        self._paused = True
        self.status_changed.emit("已暂停")
        self.running_changed.emit(False)
        self._log("info", "翻译已暂停，点击「开始」可在当前会话继续。")

    async def _resume(self) -> None:
        if self.session_id is None or not self._paused:
            return
        try:
            self._run_generation += 1
            self.loop = asyncio.get_running_loop()
            self._warned_no_audio = False
            self._paused = False

            api_key, effective_translate_key = self._resolve_api_keys()
            if not api_key:
                self._paused = True
                await self._handle_error(
                    ProviderError(provider="config", code="missing-transcribe-key", message="缺少转写 API Key，请先打开设置填写。", recoverable=False)
                )
                return

            await self._start_pipeline(api_key, effective_translate_key, log_session_start=False)
        except Exception as exc:
            self._paused = True
            await self._handle_error(
                ProviderError(provider="startup", code="resume-failed", message=str(exc), recoverable=False)
            )

    async def stop(self) -> None:
        if self.session_id is None:
            return
        self._run_generation += 1
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
        ended_session_id = self.session_id
        self.db.end_session(ended_session_id)
        self.session_changed.emit((self.db.list_sessions(), ended_session_id, True))
        self.status_changed.emit("已停止")
        self.session_id = None
        self._paused = False
        self.audio_source = None
        self.cloud_provider = None
        self.local_provider = None
        self.translator = None
        self.scheduler = None
        self.segments_by_chunk.clear()
        self.final_source_history.clear()
        self.final_translation_history.clear()
        self.last_final_source_text = ""
        self.session_started_at = None
        self.language_lock = LanguageLock(self.settings.recognition.source_language)
        self._active_transcribe_key_tail = ""
        self._active_translate_key_tail = ""
        self.running_changed.emit(False)
        self._log("info", "会话已结束。")

    async def recover_cloud(self) -> None:
        self.cloud_failures = 0
        self.degraded_local_only = False
        self.status_changed.emit("已恢复混合模式")
        self._log("info", "已手动恢复云端识别。")

    def _next_chunk_id_start(self) -> int:
        if self.session_id is None:
            return 1
        db_max = self.db.max_chunk_id(self.session_id)
        mem_max = max(self.segments_by_chunk.keys(), default=0)
        return max(db_max, mem_max) + 1

    def _handle_audio(self, pcm_bytes: bytes, sample_rate: int, channels: int) -> None:
        if not self.loop:
            return
        self.loop.call_soon_threadsafe(self._process_audio_frame, pcm_bytes, sample_rate, channels)

    def _process_audio_frame(self, pcm_bytes: bytes, sample_rate: int, channels: int) -> None:
        if self.session_id is None or self._paused:
            return
        mono = downmix_to_mono(pcm_bytes, channels)
        self.audio_packets_received += 1
        if self.audio_packets_received == 1:
            self.status_changed.emit("已接收到系统声音，正在分块识别...")
            self._log("info", f"已接收到第一帧系统声音，采样率={sample_rate}Hz，声道={channels}")
        if self.scheduler is None or self.scheduler.sample_rate != sample_rate:
            next_cid = self._next_chunk_id_start()
            if self.settings.recognition.mode == RecognitionMode.PRECISE:
                self.scheduler = ChunkScheduler(
                    sample_rate,
                    self.settings.recognition.mode,
                    step_ms=self.settings.recognition.cloud_step_ms_steady,
                    window_ms=self.settings.recognition.cloud_chunk_ms_steady,
                    next_chunk_id_start=next_cid,
                )
            else:
                self.scheduler = ChunkScheduler(
                    sample_rate,
                    self.settings.recognition.mode,
                    step_ms=self.settings.recognition.step_ms_fast,
                    window_ms=self.settings.recognition.chunk_ms_fast,
                    next_chunk_id_start=next_cid,
                )
            self._log(
                "info",
                f"已初始化分块器，step={self.scheduler._step_ms}ms，window={self.scheduler._window_ms}ms，"
                f"next_chunk_id={next_cid}",
            )
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
            if self.session_id is None or self._paused:
                return
            run_generation = self._run_generation
            text = compact_whitespace(result.text)
            previous = self.segments_by_chunk.get(result.chunk_id)
            if previous:
                text = remove_overlap(previous.source_text, text)
            elif self.last_final_source_text:
                # 新 chunk 的首条可能是草稿：也要相对「上一句定稿」去重，否则句尾/下句头会整段重复
                text = remove_adjacent_overlap(self.last_final_source_text, text)
            if not text:
                return
            locked = self.language_lock.observe(result.source_lang)
            effective_lang = locked or result.source_lang or "auto"
            translated = await self._translate(text, effective_lang)
            if self.session_id is None or run_generation != self._run_generation:
                return
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
                if result.provider == "cloud":
                    self.final_source_history.append(segment.source_text)
                    if segment.translated_text:
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
        pairs = list(zip(self.final_source_history[-6:], self.final_translation_history[-6:], strict=False))
        context = [f"源：{s} | 译：{t}" for s, t in pairs if (s or t).strip()]
        try:
            return await self.translator.translate(text, source_lang, context)
        except Exception as exc:
            await self._handle_error(
                ProviderError(provider="translator", code="translate-failed", message=str(exc), recoverable=True)
            )
            return ""

    async def _handle_error(self, error: ProviderError) -> None:
        self.error_occurred.emit(error)
        self._log("error", f"{error.provider}/{error.code}: {error.message}")
        if error.provider in {"cloud", "translator"}:
            self._log("error", f"{error.provider} config: {self._provider_context(error.provider)}")
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
        while self.session_id is not None and not self._paused:
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

    @staticmethod
    def _key_tail(value: str) -> str:
        key = (value or "").strip()
        if not key:
            return "empty"
        if len(key) <= 4:
            return key
        return key[-4:]

    def _provider_context(self, provider: str) -> str:
        if provider == "cloud":
            return (
                f"url={self.settings.recognition.transcribe_base_url}, "
                f"model={self.settings.recognition.transcribe_model}, "
                f"key_last4={self._active_transcribe_key_tail or 'empty'}"
            )
        if provider == "translator":
            return (
                f"url={self.settings.recognition.translate_base_url}, "
                f"model={self.settings.recognition.translate_model}, "
                f"key_last4={self._active_translate_key_tail or 'empty'}"
            )
        return "unknown"
