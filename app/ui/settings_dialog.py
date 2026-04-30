from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from app.models import AppSettings, OverlayMode, RecognitionMode


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, transcribe_key: str, translate_key: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.base_url_edit = QLineEdit(settings.recognition.base_url)
        self.transcribe_model_edit = QLineEdit(settings.recognition.transcribe_model)
        self.translate_model_edit = QLineEdit(settings.recognition.translate_model)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setValue(int(settings.recognition.timeout_seconds))
        self.language_combo = QComboBox()
        self.language_combo.addItems(["auto", "th", "vi", "en"])
        self.language_combo.setCurrentText(settings.recognition.source_language)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([RecognitionMode.STEADY.value, RecognitionMode.FAST.value])
        self.mode_combo.setCurrentText(settings.recognition.mode.value)
        self.overlay_combo = QComboBox()
        self.overlay_combo.addItems([OverlayMode.CLICK_THROUGH.value, OverlayMode.WINDOWED.value])
        self.overlay_combo.setCurrentText(settings.overlay_mode.value)
        self.follow_default_check = QCheckBox("跟随默认播放设备")
        self.follow_default_check.setChecked(settings.audio.follow_default_output)
        self.local_model_edit = QLineEdit(settings.recognition.local_model_size)
        self.compute_type_edit = QLineEdit(settings.local_compute_type)
        self.export_dir_edit = QLineEdit(settings.export_dir)
        self.transcribe_key_edit = QLineEdit(transcribe_key)
        self.translate_key_edit = QLineEdit(translate_key)
        self.transcribe_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.translate_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Base URL", self.base_url_edit)
        form.addRow("转写模型", self.transcribe_model_edit)
        form.addRow("翻译模型", self.translate_model_edit)
        form.addRow("源语言", self.language_combo)
        form.addRow("模式", self.mode_combo)
        form.addRow("悬浮层模式", self.overlay_combo)
        form.addRow("超时(秒)", self.timeout_spin)
        form.addRow("", self.follow_default_check)
        form.addRow("本地模型", self.local_model_edit)
        form.addRow("本地 compute_type", self.compute_type_edit)
        form.addRow("导出目录", self.export_dir_edit)
        form.addRow("转写 API Key", self.transcribe_key_edit)
        form.addRow("翻译 API Key", self.translate_key_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def build_settings(self, current: AppSettings) -> AppSettings:
        current.recognition.base_url = self.base_url_edit.text().strip()
        current.recognition.transcribe_model = self.transcribe_model_edit.text().strip()
        current.recognition.translate_model = self.translate_model_edit.text().strip()
        current.recognition.source_language = self.language_combo.currentText()
        current.recognition.mode = RecognitionMode(self.mode_combo.currentText())
        current.recognition.timeout_seconds = float(self.timeout_spin.value())
        current.audio.follow_default_output = self.follow_default_check.isChecked()
        current.recognition.local_model_size = self.local_model_edit.text().strip()
        current.local_compute_type = self.compute_type_edit.text().strip()
        current.overlay_mode = OverlayMode(self.overlay_combo.currentText())
        current.export_dir = self.export_dir_edit.text().strip()
        return current
