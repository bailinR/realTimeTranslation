from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from app.models import AppSettings, OverlayMode, RecognitionMode, TranslationDomain, TranslationStyle


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
        self.resize(560, 640)

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
        # Store primitive strings: findData() does not reliably match StrEnum with Qt's QVariant.
        self.mode_combo.addItem("精准模式（延迟略高，准确率高）", RecognitionMode.PRECISE.value)
        self.mode_combo.addItem("实时模式（延迟低，准确率一般）", RecognitionMode.REALTIME.value)
        idx = self.mode_combo.findData(settings.recognition.mode.value)
        self.mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.style_combo = QComboBox()
        self.style_combo.addItem("直播带货", TranslationStyle.LIVE_COMMERCE.value)
        self.style_combo.addItem("口语", TranslationStyle.COLLOQUIAL.value)
        self.style_combo.addItem("正式", TranslationStyle.FORMAL.value)
        sidx = self.style_combo.findData(settings.recognition.translation_style.value)
        self.style_combo.setCurrentIndex(sidx if sidx >= 0 else 0)
        self.domain_combo = QComboBox()
        self.domain_combo.addItem("不指定领域", TranslationDomain.NONE.value)
        self.domain_combo.addItem("美妆护肤", TranslationDomain.BEAUTY.value)
        self.domain_combo.addItem("服饰鞋包", TranslationDomain.FASHION.value)
        self.domain_combo.addItem("数码家电", TranslationDomain.ELECTRONICS.value)
        self.domain_combo.addItem("食品生鲜", TranslationDomain.FOOD.value)
        self.domain_combo.addItem("通用带货", TranslationDomain.GENERAL.value)
        didx = self.domain_combo.findData(settings.recognition.translation_domain.value)
        self.domain_combo.setCurrentIndex(didx if didx >= 0 else 1)
        self.glossary_edit = QPlainTextEdit()
        self.glossary_edit.setPlainText(settings.recognition.translation_glossary)
        self.glossary_edit.setPlaceholderText(
            "每行一条，例如：\n"
            "Hyaluronic acid=透明质酸\n"
            "vitamin C=维C\n"
            "# 井号开头为注释"
        )
        self.glossary_edit.setMinimumHeight(88)
        self.glossary_edit.setTabChangesFocus(True)
        self.names_edit = QPlainTextEdit()
        self.names_edit.setPlainText(settings.recognition.translation_names)
        self.names_edit.setPlaceholderText(
            "每行一条，例如：\n"
            "Lisa=丽莎\n"
            "DJ Snake=蛇爷\n"
            "# 井号开头为注释"
        )
        self.names_edit.setMinimumHeight(72)
        self.names_edit.setTabChangesFocus(True)
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
        form.addRow("翻译领域", self.domain_combo)
        glossary_tip = QLabel("术语表（品牌/成分/黑话等；可用 原文=译文，# 为注释）")
        glossary_tip.setWordWrap(True)
        glossary_tip.setStyleSheet("color: #6a7a8c; font-size: 8px;")
        form.addRow(glossary_tip)
        form.addRow(self.glossary_edit)
        names_tip = QLabel("人名/主播名表（展示名或外文=中文称呼）")
        names_tip.setWordWrap(True)
        names_tip.setStyleSheet("color: #6a7a8c; font-size: 8px;")
        form.addRow(names_tip)
        form.addRow(self.names_edit)
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
        mode_raw = self.mode_combo.currentData()
        style_raw = self.style_combo.currentData()
        try:
            current.recognition.mode = (
                RecognitionMode(mode_raw) if isinstance(mode_raw, str) else RecognitionMode.PRECISE
            )
        except ValueError:
            current.recognition.mode = RecognitionMode.PRECISE
        try:
            current.recognition.translation_style = (
                TranslationStyle(style_raw) if isinstance(style_raw, str) else TranslationStyle.LIVE_COMMERCE
            )
        except ValueError:
            current.recognition.translation_style = TranslationStyle.LIVE_COMMERCE
        domain_raw = self.domain_combo.currentData()
        try:
            current.recognition.translation_domain = (
                TranslationDomain(str(domain_raw)) if isinstance(domain_raw, str) else TranslationDomain.BEAUTY
            )
        except ValueError:
            current.recognition.translation_domain = TranslationDomain.BEAUTY
        current.recognition.translation_glossary = self.glossary_edit.toPlainText()
        current.recognition.translation_names = self.names_edit.toPlainText()
        current.recognition.timeout_seconds = float(self.timeout_spin.value())
        current.audio.follow_default_output = self.follow_default_check.isChecked()
        current.recognition.local_model_size = self.local_model_edit.text().strip()
        current.local_compute_type = self.compute_type_edit.text().strip()
        current.overlay_mode = OverlayMode(self.overlay_combo.currentText())
        current.export_dir = self.export_dir_edit.text().strip()
        return current
