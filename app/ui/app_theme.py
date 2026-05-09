from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_dark_application_theme(app: QApplication, *, ui_scale_percent: int = 100) -> None:
    """Fusion + dark palette so QDialog/QMessageBox match the main window on all Windows machines."""
    app.setStyle("Fusion")
    panel = QColor(0x12, 0x1A, 0x26)
    base = QColor(0x02, 0x09, 0x13)
    text = QColor(0xD8, 0xE3, 0xF1)
    disabled = QColor(0x6A, 0x7A, 0x8C)
    button = QColor(0x17, 0x28, 0x3B)
    highlight = QColor(0x20, 0x33, 0x49)

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, panel)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, base)
    pal.setColor(QPalette.ColorRole.AlternateBase, panel)
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, button)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.Highlight, highlight)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(0xFF, 0xFF, 0xFF))
    pal.setColor(QPalette.ColorRole.PlaceholderText, disabled)
    pal.setColor(QPalette.ColorRole.ToolTipBase, panel)
    pal.setColor(QPalette.ColorRole.ToolTipText, text)
    app.setPalette(pal)

    def sc(base: float) -> int:
        pct = max(70, min(200, ui_scale_percent))
        return max(7, round(base * pct / 100.0))

    dlg_btn = sc(9.0)
    dlg_body = max(10, sc(13.0))
    dlg_small = max(8, sc(11.0))

    app.setStyleSheet(
        f"""
        QToolTip {{ color: #d8e3f1; background-color: #121a26; border: 1px solid #31455b; font-size: {dlg_small}px; }}
        QMenu {{ background-color: #121a26; color: #d8e3f1; border: 1px solid #31455b; font-size: {dlg_small}px; }}
        QMenu::item:selected {{ background-color: #203349; }}
        QDialog {{ background-color: #121a26; font-size: {dlg_body}px; }}
        QDialog QWidget {{ color: #d8e3f1; font-family: "Microsoft YaHei UI"; }}
        QDialog QLabel {{ color: #b9c9da; }}
        QDialog QComboBox, QDialog QLineEdit, QDialog QSpinBox {{
            background-color: #020913;
            border: 1px solid #31455b;
            color: #d8e3f1;
            border-radius: 4px;
            padding: 2px 4px;
            font-size: {dlg_small}px;
        }}
        QDialog QPlainTextEdit {{
            background-color: #020913;
            color: #d8e3f1;
            border: 1px solid #31455b;
            font-size: {dlg_small}px;
        }}
        QDialog QCheckBox {{ color: #b9c9da; font-size: {dlg_small}px; }}
        QDialog QPushButton {{
            background-color: #17283b;
            border: 1px solid #31455b;
            border-radius: 5px;
            color: #edf4ff;
            padding: 4px 10px;
            font-size: {dlg_btn}px;
        }}
        QMessageBox {{ font-size: {dlg_body}px; }}
        QMessageBox QLabel {{ font-size: {dlg_body}px; }}
        QMessageBox QPushButton {{ font-size: {dlg_btn}px; }}
        QInputDialog QLabel {{ font-size: {dlg_body}px; }}
        QInputDialog QLineEdit {{ font-size: {dlg_small}px; }}
        QDialog QPushButton:hover {{ background-color: #203349; }}
        QDialog QComboBox QAbstractItemView {{
            background-color: #020913;
            color: #d8e3f1;
            selection-background-color: #203349;
            font-size: {dlg_small}px;
        }}
        """
    )
