from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from platformdirs import user_data_dir

from app.models import AppPaths, AppSettings, AudioSourceConfig, OverlayMode, RecognitionConfig, RecognitionMode


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
        mode_value = recognition_raw.get("mode", RecognitionMode.STEADY)
        try:
            recognition_raw["mode"] = mode_value if isinstance(mode_value, RecognitionMode) else RecognitionMode(str(mode_value))
        except ValueError:
            recognition_raw["mode"] = RecognitionMode.STEADY
        recognition = RecognitionConfig(**recognition_raw)
        overlay_value = raw.get("overlay_mode", OverlayMode.CLICK_THROUGH)
        try:
            overlay_mode = overlay_value if isinstance(overlay_value, OverlayMode) else OverlayMode(str(overlay_value))
        except ValueError:
            overlay_mode = OverlayMode.CLICK_THROUGH
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
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
