from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.config import SettingsManager
from app.core.controller import AppController
from app.models import AppSettings, OverlayMode, SessionRecord, SubtitleSegment
from app.store.database import Database
from app.store.settings_secrets import SecretStore
from app.ui.overlay import OverlayWindow
from app.ui.settings_dialog import SettingsDialog


class SegmentHistoryWidget(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("historyCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        self.source_label = QLabel("")
        self.translation_label = QLabel("")
        self.source_label.setObjectName("sourceLine")
        self.translation_label.setObjectName("translationLine")
        self.source_label.setWordWrap(True)
        self.translation_label.setWordWrap(True)

        layout.addWidget(self.source_label)
        layout.addWidget(self.translation_label)

    def update_segment(self, segment: SubtitleSegment) -> None:
        stamp = segment.started_at.strftime("%H:%M:%S")
        self.source_label.setText(f"[{stamp}] [{segment.source_lang}] {segment.source_text}")
        self.translation_label.setText(f"> {segment.translated_text}")


class MainWindow(QMainWindow):
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
        self.overlay.show()
        self._history_items_by_chunk: dict[int, tuple[QListWidgetItem, SegmentHistoryWidget]] = {}
        self._main_window_on_top = False
        self._overlay_visible = True
        self._drag_offset = None
        self.setWindowTitle("RealTime Translation")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(980, 700)
        self.setMinimumSize(860, 620)
        self.setWindowOpacity(0.96)

        self._build_ui()
        self._connect_signals()
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
                border: 1px solid rgba(56, 78, 104, 185);
                border-radius: 18px;
            }
            QFrame#titleBar {
                background: transparent;
                border: none;
            }
            QPushButton {
                background: #17283b;
                border: 1px solid #31455b;
                border-radius: 10px;
                color: #edf4ff;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: #203349;
            }
            QListWidget, QPlainTextEdit {
                background: #020913;
                border: 1px solid #1e3044;
                border-radius: 14px;
            }
            QFrame#liveCaptionFrame {
                background: rgba(6, 14, 23, 235);
                border: 1px solid #1e3245;
                border-radius: 12px;
            }
            QFrame#historyCard {
                background: transparent;
                border: none;
                border-radius: 0;
            }
            QLabel#sourceLine {
                color: #b9c9da;
                font-size: 14px;
                font-weight: 500;
            }
            QLabel#translationLine {
                color: #f3f7fb;
                font-size: 18px;
                font-weight: 700;
            }
            """
        )

        self.toggle_button = QPushButton("开始翻译")
        self.clear_button = QPushButton("清空当前显示")
        self.export_button = QPushButton("导出会话")
        self.settings_button = QPushButton("设置")
        self.pin_button = QPushButton("置顶主屏")
        self.overlay_visibility_button = QPushButton("隐藏字幕")
        self.overlay_button = QPushButton("切换悬浮层模式")
        self.recover_button = QPushButton("恢复云端")
        root = QWidget()
        root.setObjectName("outerRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("windowShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(12, 8, 12, 10)
        shell_layout.setSpacing(6)
        layout.addWidget(shell)

        self.title_bar = QFrame()
        self.title_bar.setObjectName("titleBar")
        self.title_bar.installEventFilter(self)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(4, 0, 4, 0)
        title_layout.setSpacing(6)
        self.title_bar.setFixedHeight(30)
        self.title_label = QLabel("realTimeTranslation")
        self.title_label.setStyleSheet("font-size: 12px; color: #d8e3f1; font-weight: 700;")
        self.minimize_button = QPushButton("最小化")
        self.close_button = QPushButton("关闭")
        self.minimize_button.setFixedHeight(24)
        self.close_button.setFixedHeight(24)
        self.minimize_button.setStyleSheet(
            "QPushButton { background: #132234; border: 1px solid #31455b; color: #d8e3f1; border-radius: 8px; padding: 2px 10px; }"
            "QPushButton:hover { background: #1c3048; }"
        )
        self.close_button.setStyleSheet(
            "QPushButton { background: #4a2229; border: 1px solid #7f4b53; color: #fff1f1; border-radius: 8px; padding: 2px 10px; }"
            "QPushButton:hover { background: #643039; }"
        )
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(self.minimize_button)
        title_layout.addWidget(self.close_button)
        shell_layout.addWidget(self.title_bar)

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(6)
        for button in (
            self.toggle_button,
            self.clear_button,
            self.export_button,
            self.settings_button,
            self.pin_button,
            self.overlay_visibility_button,
            self.overlay_button,
            self.recover_button,
        ):
            controls_row.addWidget(button)
        controls_row.addStretch(1)
        shell_layout.addLayout(controls_row)

        status_row_widget = QWidget()
        status_row_widget.setFixedHeight(22)
        status_row = QHBoxLayout(status_row_widget)
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(12)
        self.status_label = QLabel("准备就绪")
        self.status_label.setWordWrap(False)
        self.status_label.setMinimumWidth(320)
        self.status_label.setMaximumHeight(18)
        self.status_label.setStyleSheet("font-size: 12px; color: #90a7bf; padding: 0 4px;")
        self.mode_hint = QLabel(f"模式: {self.settings.recognition.mode.value}")
        self.language_hint = QLabel(f"语言: {self.settings.recognition.source_language}")
        self.stats_label = QLabel("音频帧: 0 | 分块: 0")
        self.mode_hint.setStyleSheet("font-size: 12px; color: #90a7bf;")
        self.language_hint.setStyleSheet("font-size: 12px; color: #90a7bf;")
        self.stats_label.setStyleSheet("font-size: 12px; color: #90a7bf; padding: 0 4px;")
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.mode_hint)
        status_row.addWidget(self.language_hint)
        status_row.addWidget(self.stats_label)
        shell_layout.addWidget(status_row_widget)

        splitter = QSplitter()
        shell_layout.addWidget(splitter)

        self.session_list = QListWidget()
        self.session_list.setMaximumWidth(260)
        self.session_list.setSpacing(2)
        splitter.addWidget(self.session_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.live_caption_frame = QFrame()
        self.live_caption_frame.setObjectName("liveCaptionFrame")
        self.live_caption_frame.setFrameShape(QFrame.Shape.StyledPanel)
        live_caption_layout = QVBoxLayout(self.live_caption_frame)
        live_caption_layout.setContentsMargins(14, 10, 14, 10)
        self.live_translation_label = QLabel("等待字幕...")
        self.live_translation_label.setFont(QFont("Microsoft YaHei UI", 14, QFont.Weight.Bold))
        self.live_translation_label.setStyleSheet("color: #f3f7fb;")
        self.live_translation_label.setWordWrap(True)
        self.live_translation_label.setGraphicsEffect(self._build_shadow())
        live_caption_layout.addWidget(self.live_translation_label)
        self.live_caption_frame.setMinimumHeight(56)
        self.live_caption_frame.setMaximumHeight(78)
        right_layout.addWidget(self.live_caption_frame)

        self.history_list = QListWidget()
        self.history_list.setSpacing(1)
        self.history_list.setAlternatingRowColors(False)
        right_layout.addWidget(self.history_list, 3)

        self.diagnostic_box = QPlainTextEdit()
        self.diagnostic_box.setReadOnly(True)
        self.diagnostic_box.setPlaceholderText("这里会显示采集、识别、翻译和报错日志。")
        self.diagnostic_box.setStyleSheet(
            "QPlainTextEdit { color: #8bb0c9; font-family: Consolas, 'Microsoft YaHei UI'; font-size: 12px; }"
        )
        self.diagnostic_box.setMaximumHeight(180)
        right_layout.addWidget(self.diagnostic_box, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 1080])
        self._set_toggle_button_state(False)
        self._apply_overlay_visibility_button_state()

    def _connect_signals(self) -> None:
        self.toggle_button.clicked.connect(lambda: asyncio.create_task(self._toggle_translation()))
        self.clear_button.clicked.connect(self._clear_current_view)
        self.export_button.clicked.connect(self._export_current_session)
        self.settings_button.clicked.connect(self._open_settings)
        self.pin_button.clicked.connect(self._toggle_main_window_on_top)
        self.overlay_visibility_button.clicked.connect(self._toggle_overlay_visibility)
        self.overlay_button.clicked.connect(self._toggle_overlay_mode)
        self.recover_button.clicked.connect(lambda: asyncio.create_task(self.controller.recover_cloud()))
        self.minimize_button.clicked.connect(self.showMinimized)
        self.close_button.clicked.connect(self.close)
        self.session_list.itemSelectionChanged.connect(self._load_selected_session)
        self.controller.running_changed.connect(self._set_toggle_button_state)
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

    def _set_toggle_button_state(self, running: bool) -> None:
        if running:
            self.toggle_button.setText("停止翻译")
            self.toggle_button.setStyleSheet(
                "QPushButton { background: #642b2b; border: 1px solid #8f4b4b; color: #fff1f1; border-radius: 10px; padding: 6px 12px; }"
                "QPushButton:hover { background: #7a3737; }"
            )
        else:
            self.toggle_button.setText("开始翻译")
            self.toggle_button.setStyleSheet(
                "QPushButton { background: #1f5f4d; border: 1px solid #2c8a72; color: #effff9; border-radius: 10px; padding: 6px 12px; }"
                "QPushButton:hover { background: #26765f; }"
            )

    def _toggle_main_window_on_top(self) -> None:
        self._main_window_on_top = not self._main_window_on_top
        self._apply_main_window_on_top()

    def _toggle_overlay_visibility(self) -> None:
        self._overlay_visible = not self._overlay_visible
        if self._overlay_visible:
            self.overlay.show()
            self.overlay.raise_()
        else:
            self.overlay.hide()
        self._apply_overlay_visibility_button_state()

    def _apply_overlay_visibility_button_state(self) -> None:
        if self._overlay_visible:
            self.overlay_visibility_button.setText("隐藏字幕")
            self.overlay_visibility_button.setStyleSheet(
                "QPushButton { background: #17283b; border: 1px solid #31455b; color: #edf4ff; border-radius: 10px; padding: 6px 12px; }"
                "QPushButton:hover { background: #203349; }"
            )
        else:
            self.overlay_visibility_button.setText("显示字幕")
            self.overlay_visibility_button.setStyleSheet(
                "QPushButton { background: #243244; border: 1px solid #47617d; color: #edf4ff; border-radius: 10px; padding: 6px 12px; }"
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
                "QPushButton { background: #5b4a18; border: 1px solid #8d7530; color: #fff4c7; border-radius: 10px; padding: 6px 12px; }"
                "QPushButton:hover { background: #735d1d; }"
            )
        else:
            self.pin_button.setText("置顶主屏")
            self.pin_button.setStyleSheet(
                "QPushButton { background: #17283b; border: 1px solid #31455b; color: #edf4ff; border-radius: 10px; padding: 6px 12px; }"
                "QPushButton:hover { background: #203349; }"
            )

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
        for segment in self.db.list_segments(session_id):
            self._upsert_segment(segment)

    def _upsert_segment(self, segment: SubtitleSegment) -> None:
        item_and_widget = self._history_items_by_chunk.get(segment.chunk_id)
        if item_and_widget is None:
            list_item = QListWidgetItem()
            card = SegmentHistoryWidget()
            list_item.setData(Qt.ItemDataRole.UserRole, segment.chunk_id)
            list_item.setSizeHint(card.sizeHint())
            self.history_list.addItem(list_item)
            self.history_list.setItemWidget(list_item, card)
            self._history_items_by_chunk[segment.chunk_id] = (list_item, card)
        else:
            list_item, card = item_and_widget
        card.update_segment(segment)
        list_item.setSizeHint(card.sizeHint())
        self.history_list.scrollToBottom()
        self.stats_label.setText(f"音频帧: {self.controller.audio_packets_received} | 分块: {self.controller.chunks_dispatched}")

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
        self.mode_hint.setText(f"模式: {self.settings.recognition.mode.value}")
        self.language_hint.setText(f"语言: {self.settings.recognition.source_language}")
        self._append_diagnostic("info", "设置已保存。")

    def _toggle_overlay_mode(self) -> None:
        self.settings.overlay_mode = (
            OverlayMode.WINDOWED
            if self.settings.overlay_mode == OverlayMode.CLICK_THROUGH
            else OverlayMode.CLICK_THROUGH
        )
        self.overlay.set_overlay_mode(self.settings.overlay_mode)
        self.settings_manager.save(self.settings)
        self._append_diagnostic("info", f"悬浮层模式已切换为 {self.settings.overlay_mode.value}")

    def _show_error(self, error) -> None:
        self.status_label.setText(f"{error.provider}: {error.message}")
        self._append_diagnostic("error", f"{error.provider}/{error.code}: {error.message}")

    def _update_live_caption(self, source_line: str, translated_line: str) -> None:
        self.overlay.update_text(source_line, translated_line)
        self.live_translation_label.setText(translated_line or "等待字幕...")

    def _append_diagnostic(self, level: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.diagnostic_box.appendPlainText(f"[{stamp}] {level.upper()} {message}")
        self.stats_label.setText(f"音频帧: {self.controller.audio_packets_received} | 分块: {self.controller.chunks_dispatched}")
