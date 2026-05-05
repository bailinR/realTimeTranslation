from __future__ import annotations

import asyncio

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from app.core.controller import AppController
from app.ui.main_window import MainWindow


async def _pause_if_running(controller: AppController) -> None:
    if controller.pipeline_running:
        await controller.pause()


class AppTray:
    def __init__(self, window: MainWindow, controller: AppController) -> None:
        self.window = window
        self.controller = controller
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self.tray = QSystemTrayIcon(icon, window)
        menu = QMenu()
        show_action = QAction("显示主窗口", window)
        start_action = QAction("开始/继续", window)
        stop_action = QAction("暂停", window)
        overlay_action = QAction("显示/隐藏悬浮窗", window)
        quit_action = QAction("退出", window)
        show_action.triggered.connect(window.showNormal)
        start_action.triggered.connect(lambda: asyncio.create_task(controller.start()))
        stop_action.triggered.connect(lambda: asyncio.create_task(_pause_if_running(controller)))
        overlay_action.triggered.connect(self._toggle_overlay)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(show_action)
        menu.addAction(start_action)
        menu.addAction(stop_action)
        menu.addAction(overlay_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def _toggle_overlay(self) -> None:
        self.window.set_overlay_visible(not self.window.overlay.isVisible())
