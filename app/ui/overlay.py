from __future__ import annotations

import ctypes

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget

from app.models import OverlayMode


GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


class OverlayWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("实时中文字幕")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(1220, 118)
        self.setStyleSheet(
            """
            QWidget {
                background-color: rgba(7, 18, 31, 150);
                border: none;
                border-radius: 0;
            }
            QLabel {
                background: transparent;
                border: none;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(92, 16, 92, 16)
        layout.setSpacing(6)

        self.source_label = QLabel("Waiting for subtitles...")
        self.translation_label = QLabel("等待字幕...")
        self.source_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Medium))
        self.translation_label.setFont(QFont("Microsoft YaHei UI", 18, QFont.Weight.Bold))
        self.source_label.setStyleSheet("color: #b9c9da;")
        self.translation_label.setStyleSheet("color: #f3f7fb;")
        self.source_label.setWordWrap(True)
        self.translation_label.setWordWrap(True)
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.source_label.setGraphicsEffect(self._build_shadow())
        self.translation_label.setGraphicsEffect(self._build_shadow())
        layout.addWidget(self.source_label)
        layout.addWidget(self.translation_label)
        self._drag_offset = None

    def _build_shadow(self) -> QGraphicsDropShadowEffect:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(3)
        shadow.setOffset(1, 1)
        shadow.setColor(QColor(0, 0, 0, 220))
        return shadow

    def update_text(self, source_line: str, translated_line: str) -> None:
        self.source_label.setText(source_line or "Waiting for subtitles...")
        self.translation_label.setText(translated_line or "等待字幕...")

    def set_overlay_mode(self, mode: OverlayMode) -> None:
        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if mode == OverlayMode.CLICK_THROUGH:
            style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None
