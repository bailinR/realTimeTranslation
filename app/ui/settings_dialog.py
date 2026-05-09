from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models import AppSettings, RecognitionMode, TranslationDomain, TranslationStyle


class NoWheelSpinBox(QSpinBox):
    """只允许键盘输入数值，不因滚轮改变。"""

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


@dataclass
class AppearanceFontState:
    main_history_source_font_px: int
    main_history_translation_font_px: int
    main_log_font_px: int
    overlay_source_font_size: int
    overlay_translation_font_size: int

    @staticmethod
    def from_settings(s: AppSettings) -> AppearanceFontState:
        return AppearanceFontState(
            main_history_source_font_px=int(s.main_history_source_font_px),
            main_history_translation_font_px=int(s.main_history_translation_font_px),
            main_log_font_px=int(s.main_log_font_px),
            overlay_source_font_size=int(s.overlay_source_font_size),
            overlay_translation_font_size=int(s.overlay_translation_font_size),
        )


class AppearanceFontDialog(QDialog):
    """主窗口字幕/日志与悬浮层字号；确定后由主设置对话框在点「OK」时一并保存。"""

    def __init__(self, state: AppearanceFontState, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("其他字体设置")
        self.resize(440, 360)

        layout = QVBoxLayout(self)
        tip = QLabel(
            "以下为像素基数：主窗口右侧字幕与日志还会再乘以主界面里的「整体缩放」。\n悬浮层字幕为独立字号。所有更改在主设置窗口点击「OK」后写入配置文件。"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #8bb0c9; font-size: 11px;")
        layout.addWidget(tip)

        form = QFormLayout()

        self.main_hist_src_spin = QSpinBox()
        self.main_hist_src_spin.setRange(6, 48)
        self.main_hist_src_spin.setSuffix(" px")
        self.main_hist_src_spin.setValue(state.main_history_source_font_px)

        self.main_hist_tr_spin = QSpinBox()
        self.main_hist_tr_spin.setRange(8, 64)
        self.main_hist_tr_spin.setSuffix(" px")
        self.main_hist_tr_spin.setValue(state.main_history_translation_font_px)

        self.main_log_spin = QSpinBox()
        self.main_log_spin.setRange(6, 36)
        self.main_log_spin.setSuffix(" px")
        self.main_log_spin.setValue(state.main_log_font_px)

        self.overlay_source_font_spin = QSpinBox()
        self.overlay_source_font_spin.setRange(8, 72)
        self.overlay_source_font_spin.setSuffix(" px")
        self.overlay_source_font_spin.setValue(state.overlay_source_font_size)
        self.overlay_source_font_spin.setToolTip("桌面悬浮条顶部原文（英文字幕）")

        self.overlay_translation_font_spin = QSpinBox()
        self.overlay_translation_font_spin.setRange(8, 72)
        self.overlay_translation_font_spin.setSuffix(" px")
        self.overlay_translation_font_spin.setValue(state.overlay_translation_font_size)
        self.overlay_translation_font_spin.setToolTip("桌面悬浮条底部译文（中文）")

        form.addRow("主窗口 · 字幕原文", self.main_hist_src_spin)
        form.addRow("主窗口 · 字幕译文", self.main_hist_tr_spin)
        form.addRow("主窗口 · 日志", self.main_log_spin)
        form.addRow("悬浮层 · 原文", self.overlay_source_font_spin)
        form.addRow("悬浮层 · 译文", self.overlay_translation_font_spin)

        layout.addLayout(form)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def get_state(self) -> AppearanceFontState:
        return AppearanceFontState(
            main_history_source_font_px=int(self.main_hist_src_spin.value()),
            main_history_translation_font_px=int(self.main_hist_tr_spin.value()),
            main_log_font_px=int(self.main_log_spin.value()),
            overlay_source_font_size=int(self.overlay_source_font_spin.value()),
            overlay_translation_font_size=int(self.overlay_translation_font_spin.value()),
        )


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
        self.resize(560, 480)
        self._appearance_fonts = AppearanceFontState.from_settings(settings)

        root = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        form_host = QWidget()
        form = QFormLayout(form_host)

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
        self.timeout_spin = NoWheelSpinBox()
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
        self.domain_combo.setCurrentIndex(didx if didx >= 0 else 0)

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

        tip_fs = max(7, round(8 * max(70, min(200, int(settings.ui_scale_percent))) / 100))

        self.ui_scale_spin = QSpinBox()
        self.ui_scale_spin.setRange(70, 200)
        self.ui_scale_spin.setSuffix(" %")
        self.ui_scale_spin.setValue(int(settings.ui_scale_percent))
        self.ui_scale_spin.setToolTip(
            "主窗口与对话框的基础缩放（70%～200%，100%=默认）。须点本窗口「OK」写入 settings.json。"
        )

        self.ui_scale_defaults_btn = QPushButton("默认")
        self.ui_scale_defaults_btn.setToolTip(
            "整体缩放调回 100%，并恢复主窗口/悬浮层各项字号为安装默认（仍需点本窗口「OK」才保存）。"
        )
        self.ui_scale_defaults_btn.clicked.connect(self._reset_ui_scale_and_fonts_to_defaults)

        self.other_fonts_btn = QPushButton("其他字体设置…")
        self.other_fonts_btn.setToolTip("主窗口字幕/日志与悬浮层字号；在子窗口确定后仍须在本窗口点「OK」一并保存")
        self.other_fonts_btn.clicked.connect(self._open_appearance_font_dialog)

        ui_scale_field_row = QHBoxLayout()
        ui_scale_field_row.setContentsMargins(0, 4, 0, 0)
        ui_scale_field_row.setSpacing(8)
        ui_scale_field_row.addWidget(self.ui_scale_spin, stretch=0)
        ui_scale_field_row.addWidget(self.ui_scale_defaults_btn, stretch=0)
        ui_scale_field_row.addWidget(self.other_fonts_btn, stretch=0)
        ui_scale_field_row.addStretch(1)
        ui_scale_field_wrap = QWidget()
        ui_scale_field_wrap.setLayout(ui_scale_field_row)

        self.follow_default_check = QCheckBox("跟随默认播放设备")
        self.follow_default_check.setChecked(settings.audio.follow_default_output)
        self.export_dir_edit = QLineEdit(settings.export_dir)
        self.transcribe_key_edit = QLineEdit(transcribe_key)
        self.translate_key_edit = QLineEdit(translate_key)
        self.transcribe_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.translate_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.transcribe_key_edit.setPlaceholderText("留空并确定表示清除已保存的转写 Key")
        self.translate_key_edit.setPlaceholderText("留空并确定表示清除已保存的翻译 Key（勾选右侧「与转写共用」则请求翻译时仍用转写 Key）")

        translate_key_row = QHBoxLayout()
        translate_key_row.setContentsMargins(0, 0, 0, 0)
        translate_key_row.addWidget(self.translate_key_edit, stretch=1)
        self.share_translate_btn = QPushButton("与转写共用")
        self.share_translate_btn.setCheckable(True)
        self.share_translate_btn.setChecked(settings.recognition.translate_shares_transcribe_key)
        self.share_translate_btn.setObjectName("shareTranslateKeyButton")
        self.share_translate_btn.setStyleSheet(
            "QPushButton#shareTranslateKeyButton { background: #17283b; border: 1px solid #31455b; color: #edf4ff; "
            "border-radius: 5px; font-size: 9px; padding: 2px 5px; }"
            "QPushButton#shareTranslateKeyButton:hover { background: #203349; }"
            "QPushButton#shareTranslateKeyButton:checked { background: #5b4a18; border: 1px solid #d4a017; "
            "color: #fff8e6; font-weight: 600; }"
        )
        self.share_translate_btn.setToolTip(
            "勾选并保存后：调用翻译接口时使用转写 Key；翻译 Key 仍可保存在凭据中并在下次打开时显示。"
        )
        translate_key_row.addWidget(self.share_translate_btn)
        translate_key_wrap = QWidget()
        translate_key_wrap.setLayout(translate_key_row)
        self.translate_key_edit.textChanged.connect(self._on_translate_key_text_changed)

        form.addRow("转写 Base URL", self.transcribe_base_url_combo)
        form.addRow("翻译 Base URL", self.translate_base_url_combo)
        form.addRow("转写模型", self.transcribe_model_combo)
        form.addRow("翻译模型", self.translate_model_combo)
        form.addRow("转写 API Key", self.transcribe_key_edit)
        form.addRow("翻译 API Key", translate_key_wrap)
        form.addRow("源语言", self.language_combo)
        form.addRow("识别模式", self.mode_combo)
        form.addRow("翻译风格", self.style_combo)
        form.addRow("翻译领域", self.domain_combo)

        glossary_tip = QLabel("术语表（品牌/成分/黑话等；可用 原文=译文，# 为注释）")
        glossary_tip.setWordWrap(True)
        glossary_tip.setStyleSheet(f"color: #8bb0c9; font-size: {tip_fs}px;")
        form.addRow(glossary_tip)
        form.addRow(self.glossary_edit)

        names_tip = QLabel("人名/主播名表（展示名或外文=中文称呼）")
        names_tip.setWordWrap(True)
        names_tip.setStyleSheet(f"color: #8bb0c9; font-size: {tip_fs}px;")
        form.addRow(names_tip)
        form.addRow(self.names_edit)

        form.addRow("整体缩放", ui_scale_field_wrap)

        form.addRow("超时(秒)", self.timeout_spin)
        form.addRow("", self.follow_default_check)
        form.addRow("导出目录", self.export_dir_edit)

        scroll.setWidget(form_host)
        root.addWidget(scroll, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _reset_ui_scale_and_fonts_to_defaults(self) -> None:
        self.ui_scale_spin.setValue(100)
        self._appearance_fonts = AppearanceFontState.from_settings(AppSettings())

    def _open_appearance_font_dialog(self) -> None:
        dlg = AppearanceFontDialog(self._appearance_fonts, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._appearance_fonts = dlg.get_state()

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

    def _on_translate_key_text_changed(self, text: str) -> None:
        if text.strip():
            self.share_translate_btn.setChecked(False)

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
            current.recognition.translation_style = TranslationStyle.FORMAL

        domain_raw = self.domain_combo.currentData()
        try:
            current.recognition.translation_domain = (
                TranslationDomain(str(domain_raw)) if isinstance(domain_raw, str) else TranslationDomain.NONE
            )
        except ValueError:
            current.recognition.translation_domain = TranslationDomain.NONE

        current.recognition.translation_glossary = self.glossary_edit.toPlainText()
        current.recognition.translation_names = self.names_edit.toPlainText()
        current.recognition.translate_shares_transcribe_key = self.share_translate_btn.isChecked()
        current.recognition.timeout_seconds = float(self.timeout_spin.value())
        current.audio.follow_default_output = self.follow_default_check.isChecked()
        f = self._appearance_fonts
        current.overlay_source_font_size = f.overlay_source_font_size
        current.overlay_translation_font_size = f.overlay_translation_font_size
        current.ui_scale_percent = max(70, min(200, int(self.ui_scale_spin.value())))
        current.main_history_source_font_px = f.main_history_source_font_px
        current.main_history_translation_font_px = f.main_history_translation_font_px
        current.main_log_font_px = f.main_log_font_px
        current.export_dir = self.export_dir_edit.text().strip()
        return current
