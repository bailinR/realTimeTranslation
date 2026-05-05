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
        style_value = recognition_raw.get("translation_style", TranslationStyle.LIVE_COMMERCE)
        try:
            recognition_raw["translation_style"] = (
                style_value if isinstance(style_value, TranslationStyle) else TranslationStyle(str(style_value))
            )
        except ValueError:
            recognition_raw["translation_style"] = TranslationStyle.LIVE_COMMERCE
        domain_raw = recognition_raw.get("translation_domain", TranslationDomain.BEAUTY)
        try:
            recognition_raw["translation_domain"] = (
                domain_raw if isinstance(domain_raw, TranslationDomain) else TranslationDomain(str(domain_raw))
            )
        except ValueError:
            recognition_raw["translation_domain"] = TranslationDomain.BEAUTY
        recognition_raw.setdefault("translation_glossary", "")
        recognition_raw.setdefault("translation_names", "")
        if not isinstance(recognition_raw.get("translation_glossary"), str):
            recognition_raw["translation_glossary"] = ""
        if not isinstance(recognition_raw.get("translation_names"), str):
            recognition_raw["translation_names"] = ""
        recognition = RecognitionConfig(**recognition_raw)
        overlay_value = raw.get("overlay_mode", OverlayMode.WINDOWED)
        try:
            overlay_mode = overlay_value if isinstance(overlay_value, OverlayMode) else OverlayMode(str(overlay_value))
        except ValueError:
            overlay_mode = OverlayMode.WINDOWED
        return AppSettings(
            audio=audio,
            recognition=recognition,
            overlay_mode=overlay_mode,
            export_dir=raw.get("export_dir", ""),
            local_compute_type=raw.get("local_compute_type", "int8"),
            transcribe_api_key_name=raw.get("transcribe_api_key_name", "default"),
            translate_api_key_name=raw.get("translate_api_key_name", "default"),
        )

    def save(self, settings: AppSettings) -> None:
        payload = asdict(settings)
        payload["overlay_mode"] = settings.overlay_mode.value
        payload["recognition"]["mode"] = settings.recognition.mode.value
        payload["recognition"]["translation_style"] = settings.recognition.translation_style.value
        payload["recognition"]["translation_domain"] = settings.recognition.translation_domain.value
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
