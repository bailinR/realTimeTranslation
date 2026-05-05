from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models import AppSettings, OverlayMode, RecognitionMode, TranslationDomain, TranslationStyle


class SettingsDialog(QDialog):
    LANGUAGE_OPTIONS = [
        ("自动检测", "auto"),
        ("英语", "en"),
        ("泰语", "th"),
        ("越南语", "vi"),
    ]

    TRANSCRIBE_BASE_URL_PRESETS = ("https://dashscope.aliyuncs.com/compatible-mode/v1",)
    TRANSCRIBE_MODEL_PRESETS = ("qwen3-asr-flash",)
    TRANSLATE_BASE_URL_PRESETS = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "https://api.deepseek.com/v1",
    )
    TRANSLATE_MODEL_PRESETS = ("qwen-turbo", "qwen-plus", "deepseek-chat")

    def __init__(self, settings: AppSettings, transcribe_key: str, translate_key: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(560, 680)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.transcribe_base_url_combo = self._preset_combo(
            self.TRANSCRIBE_BASE_URL_PRESETS,
            settings.recognition.transcribe_base_url,
            tip="可从下拉选择常用地址，或直接输入其它兼容 OpenAI 的 Base URL",
        )
        self.translate_base_url_combo = self._preset_combo(
            self.TRANSLATE_BASE_URL_PRESETS,
            settings.recognition.translate_base_url,
            tip="可从下拉选择常用地址，或直接输入其它兼容 OpenAI 的 Base URL",
        )
        self.transcribe_model_combo = self._preset_combo(
            self.TRANSCRIBE_MODEL_PRESETS,
            settings.recognition.transcribe_model,
            tip="可从下拉选择常用模型名，或直接输入",
        )
        self.translate_model_combo = self._preset_combo(
            self.TRANSLATE_MODEL_PRESETS,
            settings.recognition.translate_model,
            tip="可从下拉选择常用模型名，或直接输入",
        )
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
        self.mode_combo.addItem("精准模式（延迟略高，准确率更高）", RecognitionMode.PRECISE.value)
        self.mode_combo.addItem("实时模式（延迟更低，准确率略低）", RecognitionMode.REALTIME.value)
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
        self._set_compact_editor_height(self.glossary_edit, visible_rows=4)
        self.glossary_edit.setTabChangesFocus(True)

        self.names_edit = QPlainTextEdit()
        self.names_edit.setPlainText(settings.recognition.translation_names)
        self.names_edit.setPlaceholderText(
            "每行一条，例如：\n"
            "Lisa=丽莎\n"
            "DJ Snake=蛇爷\n"
            "# 井号开头为注释"
        )
        self._set_compact_editor_height(self.names_edit, visible_rows=4)
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
        self.transcribe_key_edit.setPlaceholderText("留空并确定表示清除已保存的转写 Key")
        self.translate_key_edit.setPlaceholderText("留空并确定表示清除已保存的翻译 Key（或用右侧「与转写共用」）")

        self._share_translate_with_transcribe = False

        translate_key_row = QHBoxLayout()
        translate_key_row.setContentsMargins(0, 0, 0, 0)
        translate_key_row.addWidget(self.translate_key_edit, stretch=1)
        self.share_translate_btn = QPushButton("与转写共用")
        self.share_translate_btn.setToolTip("移除单独保存的翻译 Key，翻译请求将使用上方的转写 Key")
        translate_key_row.addWidget(self.share_translate_btn)
        translate_key_wrap = QWidget()
        translate_key_wrap.setLayout(translate_key_row)
        self.share_translate_btn.clicked.connect(self._on_share_translate_clicked)
        self.translate_key_edit.textChanged.connect(self._on_translate_key_text_changed)

        form.addRow("转写 Base URL", self.transcribe_base_url_combo)
        form.addRow("翻译 Base URL", self.translate_base_url_combo)
        form.addRow("转写模型", self.transcribe_model_combo)
        form.addRow("翻译模型", self.translate_model_combo)
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
        form.addRow("翻译 API Key", translate_key_wrap)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def share_translate_with_transcribe(self) -> bool:
        return self._share_translate_with_transcribe

    def _preset_combo(self, presets: tuple[str, ...], current: str, *, tip: str = "") -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        for p in presets:
            combo.addItem(p)
        v = (current or "").strip()
        idx = combo.findText(v, Qt.MatchFlag.MatchExactly)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setEditText(v)
        if tip:
            combo.setToolTip(tip)
        le = combo.lineEdit()
        if le is not None:
            le.setPlaceholderText("可选预设或手动输入")
        return combo

    def _on_share_translate_clicked(self) -> None:
        self._share_translate_with_transcribe = True
        self.translate_key_edit.blockSignals(True)
        self.translate_key_edit.clear()
        self.translate_key_edit.blockSignals(False)

    def _on_translate_key_text_changed(self, text: str) -> None:
        if text.strip():
            self._share_translate_with_transcribe = False

    @staticmethod
    def _set_compact_editor_height(editor: QPlainTextEdit, *, visible_rows: int = 4) -> None:
        metrics = editor.fontMetrics()
        document_margin = int(editor.document().documentMargin() * 2)
        frame = int(editor.frameWidth() * 2)
        viewport_margin = 8
        height = metrics.lineSpacing() * visible_rows + document_margin + frame + viewport_margin
        editor.setFixedHeight(height)

    def build_settings(self, current: AppSettings) -> AppSettings:
        current.recognition.transcribe_base_url = self.transcribe_base_url_combo.currentText().strip()
        current.recognition.translate_base_url = self.translate_base_url_combo.currentText().strip()
        current.recognition.transcribe_model = self.transcribe_model_combo.currentText().strip()
        current.recognition.translate_model = self.translate_model_combo.currentText().strip()
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
