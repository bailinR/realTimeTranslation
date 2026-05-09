from __future__ import annotations

import ctypes
from ctypes import byref, cast
from ctypes.wintypes import MSG, POINT

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.models import OverlayMode


GWL_EXSTYLE = -20
GWL_STYLE = -16
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
WS_THICKFRAME = 0x00040000

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOOWNERZORDER = 0x0200

WM_NCHITTEST = 0x0084
HTCLIENT = 1
HTTRANSPARENT = -1


# Yellow fill + black stroke (8-way 1px only — avoids a heavy “boxed” halo).
_SUBTITLE_OUTLINE_STYLE = (
    "color: #ffe135; "
    "background: transparent; "
    "border: none; "
    "outline: none; "
    "padding: 0px; "
    "margin: 0px; "
    "text-shadow: "
    "-1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000, "
    "0 -1px 0 #000, 0 1px 0 #000, -1px 0 0 #000, 1px 0 0 #000;"
)


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
        self.resize(1220, 130)
        self._mode = OverlayMode.WINDOWED
        self.setStyleSheet(
            """
            QWidget#overlayRoot {
                background: transparent;
                border: none;
                outline: none;
            }
            QFrame#subtitlePanel {
                background-color: rgba(0, 0, 0, 150);
                border: none;
                outline: none;
                border-radius: 10px;
            }
            QWidget#subtitlePair {
                background: transparent;
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
        self.set_font_sizes(14, 18)
        self.source_label.setWordWrap(True)
        self.translation_label.setWordWrap(True)
        center = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        self.source_label.setAlignment(center)
        self.translation_label.setAlignment(center)

        self._content_frame = QFrame()
        self._content_frame.setObjectName("subtitlePanel")
        self._content_frame.setFrameShape(QFrame.Shape.NoFrame)
        self._content_frame.setLineWidth(0)
        self._content_frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._content_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.source_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.translation_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.source_label.setContentsMargins(0, 0, 0, 0)
        self.translation_label.setContentsMargins(0, 0, 0, 0)
        self.source_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.translation_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._subtitle_pair = QWidget()
        self._subtitle_pair.setObjectName("subtitlePair")
        self._subtitle_pair.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        pair_layout = QVBoxLayout(self._subtitle_pair)
        pair_layout.setContentsMargins(0, 0, 0, 0)
        pair_layout.setSpacing(0)
        pair_layout.addWidget(self.source_label)
        pair_layout.addWidget(self.translation_label)

        inner = QVBoxLayout(self._content_frame)
        inner.setContentsMargins(10, 4, 10, 4)
        inner.setSpacing(0)
        inner.addStretch(1)
        inner.addWidget(self._subtitle_pair, 0)
        inner.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)
        outer.addWidget(self._content_frame, 1)

        self._drag_offset = None

    def showEvent(self, event: QEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_windows_exstyle()

    def update_text(self, source_line: str, translated_line: str) -> None:
        self.source_label.setText(source_line or "Waiting for subtitles...")
        self.translation_label.setText(translated_line or "等待字幕...")

    def set_font_sizes(self, source_px: int, translation_px: int) -> None:
        src = max(8, min(72, int(source_px)))
        tr = max(8, min(72, int(translation_px)))
        f_src = QFont("Segoe UI")
        f_src.setPixelSize(src)
        f_src.setWeight(QFont.Weight.DemiBold)
        self.source_label.setFont(f_src)
        f_tr = QFont("Microsoft YaHei UI")
        f_tr.setPixelSize(tr)
        f_tr.setWeight(QFont.Weight.Bold)
        self.translation_label.setFont(f_tr)
        self.source_label.setStyleSheet(
            _SUBTITLE_OUTLINE_STYLE + f" font-size: {src}px; color: #ffea70; line-height: 1.0;"
        )
        self.translation_label.setStyleSheet(_SUBTITLE_OUTLINE_STYLE + f" font-size: {tr}px; line-height: 1.0;")

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
        self._strip_windows_thin_border(hwnd)

    def _strip_windows_thin_border(self, hwnd: int) -> None:
        """Remove the 1px light system frame often seen on layered frameless Tool windows."""
        try:
            gwl = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            gwl &= ~(WS_BORDER | WS_DLGFRAME | WS_THICKFRAME)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, gwl)
            flags = (
                SWP_FRAMECHANGED
                | SWP_NOMOVE
                | SWP_NOSIZE
                | SWP_NOZORDER
                | SWP_NOOWNERZORDER
                | SWP_NOACTIVATE
            )
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
        except OSError:
            return
        try:
            dwm = ctypes.windll.dwmapi
            DWMWA_BORDERLESS = 34
            val = ctypes.c_int(1)
            dwm.DwmSetWindowAttribute(hwnd, DWMWA_BORDERLESS, ctypes.byref(val), ctypes.sizeof(val))
        except OSError:
            pass

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
