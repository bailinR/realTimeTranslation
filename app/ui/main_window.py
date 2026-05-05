from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QMenu,
    QLayout,
    QPlainTextEdit,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.config import SettingsManager
from app.core.controller import AppController
from app.models import (
    AppSettings,
    OverlayMode,
    RecognitionMode,
    SessionRecord,
    SubtitleSegment,
    TranslationDomain,
    TranslationStyle,
)
from app.store.database import Database
from app.store.settings_secrets import SecretStore
from app.ui.overlay import OverlayWindow
from app.ui.settings_dialog import SettingsDialog


class SegmentHistoryWidget(QFrame):
    """Tight source/translation stack; row height from heightForWidth so multi-line source does not leave a large gap."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("historyCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(0)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self.source_label = QLabel("")
        self.translation_label = QLabel("")
        self.source_label.setObjectName("sourceLine")
        self.translation_label.setObjectName("translationLine")
        self.source_label.setWordWrap(True)
        self.translation_label.setWordWrap(True)
        self.source_label.setContentsMargins(0, 0, 0, 0)
        self.translation_label.setContentsMargins(0, 0, 0, 0)
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.source_label.setMinimumHeight(0)
        self.translation_label.setMinimumHeight(0)
        self.translation_label.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.DemiBold))

        layout.addWidget(self.source_label)
        layout.addWidget(self.translation_label)

    def row_height_for_width(self, width: int) -> int:
        m = self.layout().contentsMargins()
        inner = max(width - m.left() - m.right(), 1)
        gap = self.layout().spacing()
        h_src = self.source_label.heightForWidth(inner)
        h_tr = self.translation_label.heightForWidth(inner)
        return max(m.top() + h_src + gap + h_tr + m.bottom(), 1)

    def update_segment(self, segment: SubtitleSegment) -> None:
        self.source_label.setText(f"[{segment.source_lang}] {segment.source_text}")
        self.translation_label.setText(segment.translated_text)


class MainWindow(QMainWindow):
    LANGUAGE_LABELS = {
        "auto": "自动",
        "en": "英语",
        "th": "泰语",
        "vi": "越南语",
    }
    RECOGNITION_MODE_LABELS = {
        RecognitionMode.PRECISE: "精准",
        RecognitionMode.REALTIME: "实时",
    }
    TRANSLATION_STYLE_LABELS = {
        TranslationStyle.LIVE_COMMERCE: "带货",
        TranslationStyle.COLLOQUIAL: "口语",
        TranslationStyle.FORMAL: "正式",
    }
    TRANSLATION_DOMAIN_LABELS = {
        TranslationDomain.NONE: "不限",
        TranslationDomain.BEAUTY: "美妆",
        TranslationDomain.FASHION: "服饰",
        TranslationDomain.ELECTRONICS: "数码",
        TranslationDomain.FOOD: "食品",
        TranslationDomain.GENERAL: "通用",
    }

    def __init__(
        self,
        *,
        controller: AppController,
        db: Database,
        settings_manager: SettingsManager,
        settings: AppSettings,
        secrets: SecretStore,
        exports_dir: Path,
    ) -> None:
        super().__init__()
        self.controller = controller
        self.db = db
        self.settings_manager = settings_manager
        self.settings = settings
        self.secrets = secrets
        self.exports_dir = exports_dir
        self.overlay = OverlayWindow()
        self.overlay.set_overlay_mode(self.settings.overlay_mode)
        self._history_items_by_chunk: dict[int, tuple[QListWidgetItem, SegmentHistoryWidget]] = {}
        self._main_window_on_top = True
        self._overlay_visible = False
        self._drag_offset = None
        self._session_panel_width = 96
        self._main_splitter: QSplitter | None = None
        self.setWindowTitle("RealTime Translation")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(640, 420)
        self.setMinimumSize(360, 260)
        self.setWindowOpacity(0.88)

        self._build_ui()
        self._connect_signals()
        self._apply_main_window_on_top()
        self._load_sessions()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                color: #d8e3f1;
                font-family: "Microsoft YaHei UI";
            }
            QWidget#outerRoot {
                background: transparent;
            }
            QFrame#windowShell {
                background: rgba(7, 17, 28, 224);
                border: none;
                border-radius: 0;
            }
            QFrame#titleBar {
                background: transparent;
                border: none;
            }
            QPushButton {
                background: #17283b;
                border: 1px solid #31455b;
                border-radius: 5px;
                color: #edf4ff;
                font-size: 9px;
                padding: 2px 5px;
            }
            QPushButton:hover {
                background: #203349;
            }
            QListWidget, QPlainTextEdit {
                background: #020913;
                border: none;
                border-radius: 0;
            }
            QListWidget::item {
                padding: 0px;
            }
            QFrame#historyCard {
                background: transparent;
                border: none;
                border-radius: 0;
            }
            QLabel#sourceLine {
                color: #b9c9da;
                font-size: 9px;
                font-weight: 500;
                padding: 0px;
                margin: 0px;
                line-height: 108%;
            }
            QLabel#translationLine {
                color: #f3f7fb;
                font-size: 12px;
                font-weight: 600;
                padding: 0px;
                margin: 0px;
                line-height: 108%;
            }
            """
        )

        self.toggle_button = QPushButton("开始")
        self.clear_button = QPushButton("清空")
        self.export_button = QPushButton("导出")
        self.settings_button = QPushButton("设置")
        self.pin_button = QPushButton("置顶")
        self.overlay_visibility_button = QPushButton("字幕")
        self.overlay_button = QPushButton("字幕穿透")
        self.recover_button = QPushButton("恢复")
        self.clear_sessions_button = QPushButton("清空左侧会话")
        root = QWidget()
        root.setObjectName("outerRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("windowShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(6, 4, 6, 6)
        shell_layout.setSpacing(3)
        layout.addWidget(shell)

        self.title_bar = QFrame()
        self.title_bar.setObjectName("titleBar")
        self.title_bar.installEventFilter(self)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(4, 0, 4, 0)
        title_layout.setSpacing(4)
        self.title_bar.setFixedHeight(20)
        self.title_label = QLabel("realTimeTranslation")
        self.title_label.setStyleSheet("font-size: 9px; color: #d8e3f1; font-weight: 600;")
        self.minimize_button = QPushButton("—")
        self.close_button = QPushButton("×")
        self.minimize_button.setFixedHeight(18)
        self.close_button.setFixedHeight(18)
        self.minimize_button.setFixedWidth(22)
        self.close_button.setFixedWidth(22)
        self.minimize_button.setStyleSheet(
            "QPushButton { background: #132234; border: 1px solid #31455b; color: #d8e3f1; border-radius: 4px; font-size: 11px; padding: 0; }"
            "QPushButton:hover { background: #1c3048; }"
        )
        self.close_button.setStyleSheet(
            "QPushButton { background: #4a2229; border: 1px solid #7f4b53; color: #fff1f1; border-radius: 4px; font-size: 12px; padding: 0; }"
            "QPushButton:hover { background: #643039; }"
        )
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(self.minimize_button)
        title_layout.addWidget(self.close_button)
        shell_layout.addWidget(self.title_bar)

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(4)
        for button in (
            self.toggle_button,
            self.clear_button,
            self.export_button,
            self.settings_button,
            self.pin_button,
            self.overlay_visibility_button,
            self.overlay_button,
            self.recover_button,
            self.clear_sessions_button,
        ):
            button.setFixedHeight(20)
            controls_row.addWidget(button)
        controls_row.addStretch(1)
        shell_layout.addLayout(controls_row)

        status_row_widget = QWidget()
        status_row_widget.setFixedHeight(15)
        status_row = QHBoxLayout(status_row_widget)
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(6)
        self.status_label = QLabel("准备就绪")
        self.status_label.setWordWrap(False)
        self.status_label.setMinimumWidth(140)
        self.status_label.setMaximumHeight(14)
        self.status_label.setStyleSheet("font-size: 8px; color: #90a7bf; padding: 0 2px;")
        self.mode_hint = QLabel("")
        self.language_hint = QLabel(f"语言: {self._language_label(self.settings.recognition.source_language)}")
        self.stats_label = QLabel("帧:0|块:0")
        self.mode_hint.setStyleSheet("font-size: 8px; color: #90a7bf;")
        self.language_hint.setStyleSheet("font-size: 8px; color: #90a7bf;")
        self.stats_label.setStyleSheet("font-size: 8px; color: #90a7bf; padding: 0 2px;")
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.mode_hint)
        status_row.addWidget(self.language_hint)
        status_row.addWidget(self.stats_label)
        shell_layout.addWidget(status_row_widget)
        self._refresh_recognition_hints()

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        shell_layout.addWidget(self._main_splitter, 1)

        self.session_list = QListWidget()
        self.session_list.setMinimumWidth(56)
        self.session_list.setMaximumWidth(280)
        self.session_list.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.session_list.setStyleSheet("QListWidget { font-size: 9px; }")
        self.session_list.setSpacing(1)
        self.session_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.session_list.customContextMenuRequested.connect(self._session_list_context_menu)
        self._main_splitter.addWidget(self.session_list)

        self.history_list = QListWidget()
        self.history_list.setSpacing(5)
        self.history_list.setItemAlignment(Qt.AlignmentFlag.AlignTop)
        self.history_list.setAlternatingRowColors(False)
        self.history_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.diagnostic_box = QPlainTextEdit()
        self.diagnostic_box.setReadOnly(True)
        self.diagnostic_box.setPlaceholderText("日志")
        self.diagnostic_box.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.diagnostic_box.setStyleSheet(
            "QPlainTextEdit { color: #8bb0c9; font-family: Consolas, 'Microsoft YaHei UI'; font-size: 8px; padding: 2px 4px; }"
        )
        self.diagnostic_box.setMinimumHeight(32)
        self.diagnostic_box.setMaximumHeight(320)
        self.diagnostic_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._right_splitter = QSplitter(Qt.Orientation.Vertical)
        self._right_splitter.setObjectName("rightSplitter")
        self._right_splitter.setChildrenCollapsible(False)
        self._right_splitter.setHandleWidth(5)
        self._right_splitter.addWidget(self.history_list)
        self._right_splitter.addWidget(self.diagnostic_box)
        self._right_splitter.setStretchFactor(0, 1)
        self._right_splitter.setStretchFactor(1, 0)
        self._right_splitter.setSizes([300, 52])

        right_column = QWidget()
        right_outer = QVBoxLayout(right_column)
        right_outer.setContentsMargins(0, 0, 0, 0)
        right_outer.setSpacing(0)
        right_outer.addWidget(self._right_splitter, 1)
        right_column.setMinimumWidth(160)

        self._main_splitter.addWidget(right_column)
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.splitterMoved.connect(self._on_main_splitter_moved)
        self._main_splitter.setSizes([self._session_panel_width, 464])

        grip_row = QWidget()
        grip_layout = QHBoxLayout(grip_row)
        grip_layout.setContentsMargins(0, 0, 0, 0)
        grip_layout.setSpacing(0)
        grip_layout.addStretch(1)
        self._size_grip = QSizeGrip(self)
        self._size_grip.setStyleSheet(
            "QSizeGrip { width: 14px; height: 14px; color: #6a8aad; } QSizeGrip:hover { color: #9ec0e8; }"
        )
        grip_layout.addWidget(self._size_grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        grip_row.setFixedHeight(14)
        shell_layout.addWidget(grip_row)

        self._set_toggle_button_state(False)
        self._apply_overlay_visibility_button_state()
        self._apply_overlay_penetration_button_state()

    def _clear_all_left_sessions(self) -> None:
        if self.controller.session_id is not None:
            QMessageBox.warning(self, "无法清空", "请先停止翻译，再清空全部会话记录。")
            return
        count = len(self.db.list_sessions())
        if count == 0:
            QMessageBox.information(self, "清空会话", "左侧没有可删除的会话记录。")
            return
        reply = QMessageBox.question(
            self,
            "清空全部会话",
            f"确定删除全部 {count} 条会话及其字幕？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_all_sessions()
        self.controller.session_changed.emit(self.db.list_sessions())
        self.history_list.clear()
        self._history_items_by_chunk.clear()
        self._update_live_caption("", "")

    def _connect_signals(self) -> None:
        self.toggle_button.clicked.connect(lambda: asyncio.create_task(self._toggle_translation()))
        self.clear_button.clicked.connect(self._clear_current_view)
        self.export_button.clicked.connect(self._export_current_session)
        self.settings_button.clicked.connect(self._open_settings)
        self.pin_button.clicked.connect(self._toggle_main_window_on_top)
        self.overlay_visibility_button.clicked.connect(self._toggle_overlay_visibility)
        self.overlay_button.clicked.connect(self._toggle_overlay_mode)
        self.recover_button.clicked.connect(lambda: asyncio.create_task(self.controller.recover_cloud()))
        self.clear_sessions_button.clicked.connect(self._clear_all_left_sessions)
        self.minimize_button.clicked.connect(self.showMinimized)
        self.close_button.clicked.connect(self.close)
        self.session_list.itemSelectionChanged.connect(self._load_selected_session)
        self._session_delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self.session_list)
        self._session_delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._session_delete_shortcut.activated.connect(self._delete_selected_session)
        self.controller.running_changed.connect(self._on_running_changed)
        self.controller.segment_updated.connect(self._upsert_segment)
        self.controller.session_changed.connect(self._refresh_sessions)
        self.controller.status_changed.connect(self.status_label.setText)
        self.controller.error_occurred.connect(self._show_error)
        self.controller.overlay_updated.connect(self._update_live_caption)
        self.controller.diagnostic_logged.connect(self._append_diagnostic)

    def _build_shadow(self) -> QGraphicsDropShadowEffect:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(4)
        shadow.setOffset(1, 1)
        shadow.setColor(QColor(0, 0, 0, 220))
        return shadow

    async def _toggle_translation(self) -> None:
        if self.controller.session_id is None:
            await self.controller.start()
        else:
            await self.controller.stop()

    def _on_running_changed(self, running: bool) -> None:
        self._set_toggle_button_state(running)
        if running and self.controller.session_id is not None:
            self._focus_active_session(self.controller.session_id)

    def _focus_active_session(self, session_id: int) -> None:
        for row in range(self.session_list.count()):
            item = self.session_list.item(row)
            if item is None:
                continue
            if item.data(Qt.ItemDataRole.UserRole) == session_id:
                self.session_list.setCurrentRow(row)
                self.session_list.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtTop)
                break

    def _set_toggle_button_state(self, running: bool) -> None:
        if running:
            self.toggle_button.setText("停止")
            self.toggle_button.setStyleSheet(
                "QPushButton { background: #642b2b; border: 1px solid #8f4b4b; color: #fff1f1; border-radius: 5px; font-size: 9px; padding: 2px 5px; }"
                "QPushButton:hover { background: #7a3737; }"
            )
        else:
            self.toggle_button.setText("开始")
            self.toggle_button.setStyleSheet(
                "QPushButton { background: #1f5f4d; border: 1px solid #2c8a72; color: #effff9; border-radius: 5px; font-size: 9px; padding: 2px 5px; }"
                "QPushButton:hover { background: #26765f; }"
            )

    def _toggle_main_window_on_top(self) -> None:
        self._main_window_on_top = not self._main_window_on_top
        self._apply_main_window_on_top()

    def _toggle_overlay_visibility(self) -> None:
        self.set_overlay_visible(not self._overlay_visible)

    def set_overlay_visible(self, visible: bool) -> None:
        self._overlay_visible = visible
        if self._overlay_visible:
            self.overlay.show()
            self.overlay.raise_()
        else:
            self.overlay.hide()
        self._apply_overlay_visibility_button_state()

    def _apply_overlay_penetration_button_state(self) -> None:
        """Lit style when subtitle is click-through; subdued when windowed (captures mouse)."""
        if self.settings.overlay_mode == OverlayMode.CLICK_THROUGH:
            self.overlay_button.setStyleSheet(
                "QPushButton { background: #6b4a12; border: 1px solid #d4a017; color: #fff8e6; border-radius: 5px; "
                "font-size: 9px; padding: 2px 5px; font-weight: 600; }"
                "QPushButton:hover { background: #7d5a18; }"
            )
        else:
            self.overlay_button.setStyleSheet(
                "QPushButton { background: #17283b; border: 1px solid #31455b; color: #edf4ff; border-radius: 5px; "
                "font-size: 9px; padding: 2px 5px; }"
                "QPushButton:hover { background: #203349; }"
            )

    def _apply_overlay_visibility_button_state(self) -> None:
        if self._overlay_visible:
            self.overlay_visibility_button.setText("字幕关")
            self.overlay_visibility_button.setStyleSheet(
                "QPushButton { background: #17283b; border: 1px solid #31455b; color: #edf4ff; border-radius: 5px; font-size: 9px; padding: 2px 5px; }"
                "QPushButton:hover { background: #203349; }"
            )
        else:
            self.overlay_visibility_button.setText("字幕开")
            self.overlay_visibility_button.setStyleSheet(
                "QPushButton { background: #243244; border: 1px solid #47617d; color: #edf4ff; border-radius: 5px; font-size: 9px; padding: 2px 5px; }"
                "QPushButton:hover { background: #30445d; }"
            )

    def _apply_main_window_on_top(self) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self._main_window_on_top)
        self.show()
        self.raise_()
        self.activateWindow()
        if self._main_window_on_top:
            self.pin_button.setText("取消置顶")
            self.pin_button.setStyleSheet(
                "QPushButton { background: #5b4a18; border: 1px solid #8d7530; color: #fff4c7; border-radius: 5px; font-size: 9px; padding: 2px 5px; }"
                "QPushButton:hover { background: #735d1d; }"
            )
        else:
            self.pin_button.setText("置顶")
            self.pin_button.setStyleSheet(
                "QPushButton { background: #17283b; border: 1px solid #31455b; color: #edf4ff; border-radius: 5px; font-size: 9px; padding: 2px 5px; }"
                "QPushButton:hover { background: #203349; }"
            )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_main_splitter_for_resize()
        self._reflow_history_row_heights()

    def _reflow_history_row_heights(self) -> None:
        if not self._history_items_by_chunk:
            return
        vpw = max(self.history_list.viewport().width() - 2, 40)
        for _cid, (list_item, card) in self._history_items_by_chunk.items():
            list_item.setSizeHint(QSize(vpw, card.row_height_for_width(vpw)))
        self.history_list.scheduleDelayedItemsLayout()

    def _on_main_splitter_moved(self, _pos: int, _index: int) -> None:
        self._session_panel_width = max(
            self.session_list.minimumWidth(),
            min(self.session_list.width(), self.session_list.maximumWidth()),
        )

    def _sync_main_splitter_for_resize(self) -> None:
        sp = self._main_splitter
        if sp is None or sp.width() < 1:
            return
        hw = sp.handleWidth()
        total = sp.width()
        left = int(
            max(
                self.session_list.minimumWidth(),
                min(self._session_panel_width, self.session_list.maximumWidth()),
            )
        )
        right = total - left - hw
        min_right = 120
        if right < min_right:
            right = min_right
            left = max(self.session_list.minimumWidth(), total - hw - right)
        cur = sp.sizes()
        if len(cur) == 2 and cur[0] == left and cur[1] == right:
            return
        sp.setSizes([left, right])

    def eventFilter(self, watched, event) -> bool:
        if watched is self.title_bar:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            if event.type() == QEvent.Type.MouseMove and self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_offset = None
                return True
        return super().eventFilter(watched, event)

    def _load_sessions(self) -> None:
        self._refresh_sessions(self.db.list_sessions())

    def _session_list_context_menu(self, pos) -> None:
        item = self.session_list.itemAt(pos)
        if item is None:
            return
        self.session_list.setCurrentItem(item)
        menu = QMenu(self)
        delete_action = menu.addAction("删除记录")
        chosen = menu.exec(self.session_list.mapToGlobal(pos))
        if chosen is delete_action:
            self._delete_selected_session()

    def _delete_selected_session(self) -> None:
        item = self.session_list.currentItem()
        if item is None:
            return
        row = self.session_list.row(item)
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if self.controller.session_id is not None and self.controller.session_id == session_id:
            QMessageBox.warning(self, "无法删除", "当前会话正在翻译中，请先停止后再删除记录。")
            return
        reply = QMessageBox.question(
            self,
            "删除会话",
            f"确定删除会话 #{session_id}？数据库中的该条记录将不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_session(session_id)
        except ValueError:
            QMessageBox.warning(self, "删除失败", "未找到该会话，可能已被删除。")
            self.controller.session_changed.emit(self.db.list_sessions())
            return
        sessions = self.db.list_sessions()
        self.controller.session_changed.emit(sessions)
        if self.session_list.count() > 0:
            pick = min(row, self.session_list.count() - 1)
            self.session_list.setCurrentRow(pick)
        else:
            self.history_list.clear()
            self._history_items_by_chunk.clear()
            self._update_live_caption("", "")

    def _refresh_sessions(self, sessions: list[SessionRecord]) -> None:
        self.session_list.clear()
        for session in sessions:
            label = f"#{session.session_id} {session.created_at:%m-%d %H:%M} {session.mode}/{session.source_language}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, session.session_id)
            self.session_list.addItem(item)

    def _load_selected_session(self) -> None:
        item = self.session_list.currentItem()
        if item is None:
            return
        session_id = item.data(Qt.ItemDataRole.UserRole)
        self.history_list.clear()
        self._history_items_by_chunk.clear()
        segments = self.db.list_segments(session_id)
        for segment in segments:
            self._upsert_segment(segment)
        if not segments:
            self.history_list.scrollToTop()

    def _upsert_segment(self, segment: SubtitleSegment) -> None:
        item_and_widget = self._history_items_by_chunk.get(segment.chunk_id)
        if item_and_widget is None:
            list_item = QListWidgetItem()
            card = SegmentHistoryWidget()
            list_item.setData(Qt.ItemDataRole.UserRole, segment.chunk_id)
            self.history_list.addItem(list_item)
            self.history_list.setItemWidget(list_item, card)
            self._history_items_by_chunk[segment.chunk_id] = (list_item, card)
        else:
            list_item, card = item_and_widget
        card.update_segment(segment)
        vpw = max(self.history_list.viewport().width() - 2, 40)
        row_h = card.row_height_for_width(vpw)
        list_item.setSizeHint(QSize(vpw, row_h))
        self.history_list.scheduleDelayedItemsLayout()
        self.history_list.scrollToBottom()
        self.stats_label.setText(
            f"帧:{self.controller.audio_packets_received}|块:{self.controller.chunks_dispatched}"
        )

    def _find_chunk_row(self, chunk_id: int) -> int | None:
        item_and_widget = self._history_items_by_chunk.get(chunk_id)
        if item_and_widget is None:
            return None
        list_item, _card = item_and_widget
        return self.history_list.row(list_item)

    def _clear_current_view(self) -> None:
        self.history_list.clear()
        self._history_items_by_chunk.clear()
        self._update_live_caption("", "")
        self.diagnostic_box.clear()

    def _export_current_session(self) -> None:
        item = self.session_list.currentItem()
        if item is None:
            QMessageBox.information(self, "导出会话", "请先选择一个会话。")
            return
        session_id = item.data(Qt.ItemDataRole.UserRole)
        base_dir = Path(self.settings.export_dir) if self.settings.export_dir else self.exports_dir
        base_dir.mkdir(parents=True, exist_ok=True)
        target_dir = QFileDialog.getExistingDirectory(self, "选择导出目录", str(base_dir))
        if not target_dir:
            return
        txt_path = Path(target_dir) / f"session-{session_id}.txt"
        srt_path = Path(target_dir) / f"session-{session_id}.srt"
        self.db.export_txt(session_id, txt_path)
        self.db.export_srt(session_id, srt_path)
        QMessageBox.information(self, "导出成功", f"已导出到:\n{txt_path}\n{srt_path}")

    def _open_settings(self) -> None:
        dialog = SettingsDialog(
            self.settings,
            self.secrets.get(self.settings.transcribe_api_key_name),
            self.secrets.get(self.settings.translate_api_key_name),
            self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self.settings = dialog.build_settings(self.settings)
        self.settings_manager.save(self.settings)
        self.secrets.set(self.settings.transcribe_api_key_name, dialog.transcribe_key_edit.text().strip())
        self.secrets.set(self.settings.translate_api_key_name, dialog.translate_key_edit.text().strip())
        self.overlay.set_overlay_mode(self.settings.overlay_mode)
        self._refresh_recognition_hints()
        self.language_hint.setText(f"语言: {self._language_label(self.settings.recognition.source_language)}")
        self._apply_overlay_penetration_button_state()
        self._append_diagnostic("info", "设置已保存。")

    def _toggle_overlay_mode(self) -> None:
        self.settings.overlay_mode = (
            OverlayMode.WINDOWED
            if self.settings.overlay_mode == OverlayMode.CLICK_THROUGH
            else OverlayMode.CLICK_THROUGH
        )
        self.overlay.set_overlay_mode(self.settings.overlay_mode)
        self.settings_manager.save(self.settings)
        self._apply_overlay_penetration_button_state()
        self._append_diagnostic("info", f"悬浮层模式已切换为 {self.settings.overlay_mode.value}")

    def _show_error(self, error) -> None:
        self.status_label.setText(f"{error.provider}: {error.message}")
        self._append_diagnostic("error", f"{error.provider}/{error.code}: {error.message}")

    def _update_live_caption(self, source_line: str, translated_line: str) -> None:
        self.overlay.update_text(source_line, translated_line)

    def _append_diagnostic(self, level: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.diagnostic_box.appendPlainText(f"[{stamp}] {level.upper()} {message}")
        self.stats_label.setText(
            f"帧:{self.controller.audio_packets_received}|块:{self.controller.chunks_dispatched}"
        )

    def _language_label(self, language_code: str) -> str:
        return self.LANGUAGE_LABELS.get(language_code, language_code)

    def _refresh_recognition_hints(self) -> None:
        m = self.RECOGNITION_MODE_LABELS.get(
            self.settings.recognition.mode, self.settings.recognition.mode.value
        )
        s = self.TRANSLATION_STYLE_LABELS.get(
            self.settings.recognition.translation_style, self.settings.recognition.translation_style.value
        )
        d = self.TRANSLATION_DOMAIN_LABELS.get(
            self.settings.recognition.translation_domain, self.settings.recognition.translation_domain.value
        )
        self.mode_hint.setText(f"识别:{m} | 风格:{s} | 领域:{d}")
