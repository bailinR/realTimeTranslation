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

from app.models import AppSettings, OverlayMode, RecognitionMode, TranslationStyle


class SettingsDialog(QDialog):
    LANGUAGE_OPTIONS = [
        ("自动检测", "auto"),
        ("英语", "en"),
        ("泰语", "th"),
        ("越南语", "vi"),
    ]

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
        for label, value in self.LANGUAGE_OPTIONS:
            self.language_combo.addItem(label, value)
        current_language_index = self.language_combo.findData(settings.recognition.source_language)
        if current_language_index >= 0:
            self.language_combo.setCurrentIndex(current_language_index)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("精准模式（延迟略高，准确率高）", RecognitionMode.PRECISE)
        self.mode_combo.addItem("实时模式（延迟低，准确率一般）", RecognitionMode.REALTIME)
        idx = self.mode_combo.findData(settings.recognition.mode)
        self.mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.style_combo = QComboBox()
        self.style_combo.addItem("直播带货", TranslationStyle.LIVE_COMMERCE)
        self.style_combo.addItem("口语", TranslationStyle.COLLOQUIAL)
        self.style_combo.addItem("正式", TranslationStyle.FORMAL)
        sidx = self.style_combo.findData(settings.recognition.translation_style)
        self.style_combo.setCurrentIndex(sidx if sidx >= 0 else 0)
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
        form.addRow("识别模式", self.mode_combo)
        form.addRow("翻译风格", self.style_combo)
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
        current.recognition.source_language = self.language_combo.currentData()
        mode = self.mode_combo.currentData()
        style = self.style_combo.currentData()
        current.recognition.mode = mode if isinstance(mode, RecognitionMode) else RecognitionMode.PRECISE
        current.recognition.translation_style = (
            style if isinstance(style, TranslationStyle) else TranslationStyle.LIVE_COMMERCE
        )
        current.recognition.timeout_seconds = float(self.timeout_spin.value())
        current.audio.follow_default_output = self.follow_default_check.isChecked()
        current.recognition.local_model_size = self.local_model_edit.text().strip()
        current.local_compute_type = self.compute_type_edit.text().strip()
        current.overlay_mode = OverlayMode(self.overlay_combo.currentText())
        current.export_dir = self.export_dir_edit.text().strip()
        return current
