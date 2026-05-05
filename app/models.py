from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class RecognitionMode(StrEnum):
    """precise=长窗口高准确；realtime=短窗口低延迟，并启用本地草稿+云端混合。"""

    PRECISE = "precise"
    REALTIME = "realtime"


class TranslationStyle(StrEnum):
    """翻译语气与场景。"""

    LIVE_COMMERCE = "live_commerce"
    COLLOQUIAL = "colloquial"
    FORMAL = "formal"


class TranslationDomain(StrEnum):
    """翻译领域（影响系统提示中的场景约束）；none=不额外限定。"""

    NONE = "none"
    BEAUTY = "beauty"
    FASHION = "fashion"
    ELECTRONICS = "electronics"
    FOOD = "food"
    GENERAL = "general"


class SubtitleStatus(StrEnum):
    DRAFT = "draft"
    FINAL = "final"
    ERROR = "error"


class OverlayMode(StrEnum):
    CLICK_THROUGH = "click_through"
    WINDOWED = "windowed"


@dataclass(slots=True)
class AudioSourceConfig:
    device_index: int | None = None
    follow_default_output: bool = True
    frames_per_buffer: int = 2048


@dataclass(slots=True)
class RecognitionConfig:
    mode: RecognitionMode = RecognitionMode.PRECISE
    translation_style: TranslationStyle = TranslationStyle.LIVE_COMMERCE
    translation_domain: TranslationDomain = TranslationDomain.BEAUTY
    translation_glossary: str = ""
    translation_names: str = ""
    source_language: str = "auto"
    transcribe_model: str = "qwen3-asr-flash"
    translate_model: str = "qwen-plus"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    timeout_seconds: float = 30.0
    local_model_size: str = "small"
    cloud_chunk_ms_steady: int = 3400
    cloud_step_ms_steady: int = 2800
    chunk_ms_fast: int = 1800
    step_ms_fast: int = 1100
    cloud_fail_threshold: int = 3


@dataclass(slots=True)
class AppSettings:
    audio: AudioSourceConfig = field(default_factory=AudioSourceConfig)
    recognition: RecognitionConfig = field(default_factory=RecognitionConfig)
    overlay_mode: OverlayMode = OverlayMode.WINDOWED
    export_dir: str = ""
    local_compute_type: str = "int8"
    transcribe_api_key_name: str = "default"
    translate_api_key_name: str = "default"


@dataclass(slots=True)
class AudioChunk:
    chunk_id: int
    pcm_bytes: bytes
    sample_rate: int
    channels: int
    start_ms: int
    end_ms: int


@dataclass(slots=True)
class TranscriptResult:
    chunk_id: int
    start_ms: int
    end_ms: int
    text: str
    source_lang: str
    provider: str
    is_final: bool


@dataclass(slots=True)
class SubtitleSegment:
    seq: int
    session_id: int
    chunk_id: int
    started_at: datetime
    ended_at: datetime
    source_lang: str
    source_text: str
    translated_text: str
    status: SubtitleStatus
    provider: str


@dataclass(slots=True)
class ProviderError:
    provider: str
    code: str
    message: str
    recoverable: bool = True


@dataclass(slots=True)
class SessionRecord:
    session_id: int
    created_at: datetime
    ended_at: datetime | None
    mode: str
    source_language: str


@dataclass(slots=True)
class AppPaths:
    root: Path
    db_path: Path
    settings_path: Path
    exports_dir: Path
    logs_dir: Path
