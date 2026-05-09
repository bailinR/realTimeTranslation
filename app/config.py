from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from platformdirs import user_data_dir

from app.models import (
    AppPaths,
    AppSettings,
    AudioSourceConfig,
    OverlayMode,
    RecognitionConfig,
    RecognitionMode,
    TranslationDomain,
    TranslationStyle,
)


APP_NAME = "RealTimeTranslation"
SECRET_SERVICE = "realtime-translation"

# Used when keyring has no transcribe key (e.g. first launch). Replace for your distribution.
DEFAULT_TRANSCRIBE_API_KEY = "sk-faa688a28c1546a8b74ab658bd1c9cc2"

_FONT_SIZE_MIN = 8
_FONT_SIZE_MAX = 72

UI_SCALE_MIN = 70
UI_SCALE_MAX = 200


def _clamp_ui_scale(value: object, default: int = 100) -> int:
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(UI_SCALE_MIN, min(UI_SCALE_MAX, n))


def _clamp_positive_font(value: object, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _clamp_overlay_font(value: object, default: int) -> int:
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(_FONT_SIZE_MIN, min(_FONT_SIZE_MAX, n))


def get_app_paths() -> AppPaths:
    root = Path(user_data_dir(APP_NAME, roaming=True))
    exports_dir = root / "exports"
    logs_dir = root / "logs"
    for path in (root, exports_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)
    return AppPaths(
        root=root,
        db_path=root / "app.db",
        settings_path=root / "settings.json",
        exports_dir=exports_dir,
        logs_dir=logs_dir,
    )


class SettingsManager:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        audio = AudioSourceConfig(**raw.get("audio", {}))
        recognition_raw = dict(raw.get("recognition", {}))
        mode_value = recognition_raw.get("mode", RecognitionMode.PRECISE)
        if isinstance(mode_value, RecognitionMode):
            recognition_raw["mode"] = mode_value
        else:
            legacy = {"steady": RecognitionMode.PRECISE, "fast": RecognitionMode.REALTIME}
            if str(mode_value) in legacy:
                recognition_raw["mode"] = legacy[str(mode_value)]
            else:
                try:
                    recognition_raw["mode"] = RecognitionMode(str(mode_value))
                except ValueError:
                    recognition_raw["mode"] = RecognitionMode.PRECISE
        style_value = recognition_raw.get("translation_style", TranslationStyle.FORMAL)
        try:
            recognition_raw["translation_style"] = (
                style_value if isinstance(style_value, TranslationStyle) else TranslationStyle(str(style_value))
            )
        except ValueError:
            recognition_raw["translation_style"] = TranslationStyle.FORMAL
        domain_raw = recognition_raw.get("translation_domain", TranslationDomain.NONE)
        try:
            recognition_raw["translation_domain"] = (
                domain_raw if isinstance(domain_raw, TranslationDomain) else TranslationDomain(str(domain_raw))
            )
        except ValueError:
            recognition_raw["translation_domain"] = TranslationDomain.NONE
        legacy_base_url = recognition_raw.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        transcribe_base_url = recognition_raw.get("transcribe_base_url", legacy_base_url)
        translate_base_url = recognition_raw.get("translate_base_url", legacy_base_url)
        recognition_raw["transcribe_base_url"] = (
            transcribe_base_url if isinstance(transcribe_base_url, str) else str(legacy_base_url)
        )
        recognition_raw["translate_base_url"] = (
            translate_base_url if isinstance(translate_base_url, str) else str(legacy_base_url)
        )
        recognition_raw.pop("base_url", None)
        recognition_raw.setdefault("translation_glossary", "")
        recognition_raw.setdefault("translation_names", "")
        if not isinstance(recognition_raw.get("translation_glossary"), str):
            recognition_raw["translation_glossary"] = ""
        if not isinstance(recognition_raw.get("translation_names"), str):
            recognition_raw["translation_names"] = ""
        _share_t = recognition_raw.get("translate_shares_transcribe_key", False)
        recognition_raw["translate_shares_transcribe_key"] = _share_t if isinstance(_share_t, bool) else False
        recognition = RecognitionConfig(**recognition_raw)
        overlay_value = raw.get("overlay_mode", OverlayMode.WINDOWED)
        try:
            overlay_mode = overlay_value if isinstance(overlay_value, OverlayMode) else OverlayMode(str(overlay_value))
        except ValueError:
            overlay_mode = OverlayMode.WINDOWED
        transcribe_api_key_name = raw.get("transcribe_api_key_name", "transcribe")
        translate_api_key_name = raw.get("translate_api_key_name", "translate")
        if transcribe_api_key_name == "default" and translate_api_key_name == "default":
            transcribe_api_key_name = "transcribe"
            translate_api_key_name = "translate"
        return AppSettings(
            audio=audio,
            recognition=recognition,
            overlay_mode=overlay_mode,
            overlay_source_font_size=_clamp_overlay_font(raw.get("overlay_source_font_size", 14), 14),
            overlay_translation_font_size=_clamp_overlay_font(
                raw.get("overlay_translation_font_size", 18), 18
            ),
            ui_scale_percent=_clamp_ui_scale(raw.get("ui_scale_percent", 100)),
            main_history_source_font_px=_clamp_positive_font(
                raw.get("main_history_source_font_px", 9), 9, 6, 48
            ),
            main_history_translation_font_px=_clamp_positive_font(
                raw.get("main_history_translation_font_px", 12), 12, 8, 64
            ),
            main_log_font_px=_clamp_positive_font(raw.get("main_log_font_px", 8), 8, 6, 36),
            export_dir=raw.get("export_dir", ""),
            local_compute_type=raw.get("local_compute_type", "int8"),
            transcribe_api_key_name=transcribe_api_key_name,
            translate_api_key_name=translate_api_key_name,
        )

    def save(self, settings: AppSettings) -> None:
        payload = asdict(settings)
        payload["overlay_mode"] = settings.overlay_mode.value
        payload["recognition"]["mode"] = settings.recognition.mode.value
        payload["recognition"]["translation_style"] = settings.recognition.translation_style.value
        payload["recognition"]["translation_domain"] = settings.recognition.translation_domain.value
        payload["recognition"].pop("base_url", None)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
