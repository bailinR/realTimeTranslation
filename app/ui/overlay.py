from __future__ import annotations

import ctypes
from ctypes import byref, cast
from ctypes.wintypes import MSG, POINT

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.models import OverlayMode


GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

WM_NCHITTEST = 0x0084
HTCLIENT = 1
HTTRANSPARENT = -1


def _label_shadow() -> QGraphicsDropShadowEffect:
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(6)
    shadow.setOffset(0, 1)
    shadow.setColor(QColor(0, 0, 0, 220))
    return shadow


class OverlayWindow(QWidget):
    """Frameless subtitle bar. WINDOWED: full bar draggable. CLICK_THROUGH: text panel passes clicks."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("实时中文字幕")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(1220, 118)
        self._mode = OverlayMode.WINDOWED
        self.setStyleSheet(
            """
            QWidget#overlayRoot {
                background-color: rgba(12, 14, 18, 200);
                border: none;
                outline: none;
            }
            QFrame#subtitlePanel {
                background-color: transparent;
                border: none;
            }
            QLabel {
                background: transparent;
                border: none;
                outline: none;
            }
            """
        )
        self.setObjectName("overlayRoot")

        self.source_label = QLabel("Waiting for subtitles...")
        self.translation_label = QLabel("等待字幕...")
        self.source_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Medium))
        self.translation_label.setFont(QFont("Microsoft YaHei UI", 18, QFont.Weight.Bold))
        self.source_label.setStyleSheet("color: #f1f5f9;")
        self.translation_label.setStyleSheet("color: #ffffff;")
        self.source_label.setWordWrap(True)
        self.translation_label.setWordWrap(True)
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.source_label.setGraphicsEffect(_label_shadow())
        self.translation_label.setGraphicsEffect(_label_shadow())

        self._content_frame = QFrame()
        self._content_frame.setObjectName("subtitlePanel")
        self._content_frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._content_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.source_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.translation_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        inner = QVBoxLayout(self._content_frame)
        inner.setContentsMargins(6, 4, 6, 4)
        inner.setSpacing(4)
        inner.addWidget(self.source_label)
        inner.addWidget(self.translation_label)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 10, 20, 10)
        outer.setSpacing(0)
        outer.addWidget(self._content_frame, 1)

        self._drag_offset = None

    def showEvent(self, event: QEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_windows_exstyle()

    def update_text(self, source_line: str, translated_line: str) -> None:
        self.source_label.setText(source_line or "Waiting for subtitles...")
        self.translation_label.setText(translated_line or "等待字幕...")

    def set_overlay_mode(self, mode: OverlayMode) -> None:
        self._mode = mode
        self._apply_windows_exstyle()

    def _apply_windows_exstyle(self) -> None:
        hwnd = int(self.winId())
        if hwnd == 0:
            return
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED
        style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def nativeEvent(self, eventType, message):  # noqa: N802
        if b"windows_generic_MSG" not in bytes(eventType):
            return super().nativeEvent(eventType, message)
        msg = cast(int(message), ctypes.POINTER(MSG)).contents
        if msg.message != WM_NCHITTEST or self._mode != OverlayMode.CLICK_THROUGH:
            return super().nativeEvent(eventType, message)
        hwnd = int(self.winId())
        if hwnd == 0:
            return super().nativeEvent(eventType, message)
        x = ctypes.c_int16(msg.lParam & 0xFFFF).value
        y = ctypes.c_int16((msg.lParam >> 16) & 0xFFFF).value
        pt = POINT(x, y)
        ctypes.windll.user32.ScreenToClient(hwnd, byref(pt))
        qpt = QPoint(int(pt.x), int(pt.y))
        if self._content_frame.geometry().contains(qpt):
            return True, HTTRANSPARENT
        return True, HTCLIENT

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
