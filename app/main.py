from __future__ import annotations

import asyncio
import sys

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from app.config import SettingsManager, get_app_paths
from app.core.controller import AppController
from app.core.events import EventBus
from app.logging_config import setup_logging
from app.store.database import Database
from app.store.settings_secrets import SecretStore
from app.ui.main_window import MainWindow
from app.ui.tray import AppTray


def main() -> int:
    app = QApplication(sys.argv)
    paths = get_app_paths()
    setup_logging(paths.logs_dir)
    settings_manager = SettingsManager(paths.settings_path)
    settings = settings_manager.load()
    db = Database(paths.db_path)
    secrets = SecretStore()
    controller = AppController(settings, paths, db, secrets, EventBus())
    window = MainWindow(
        controller=controller,
        db=db,
        settings_manager=settings_manager,
        settings=settings,
        secrets=secrets,
        exports_dir=paths.exports_dir,
    )
    window.tray = AppTray(window, controller)
    window.show()

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    app.aboutToQuit.connect(lambda: asyncio.create_task(controller.stop()))
    app.aboutToQuit.connect(db.close)
    with loop:
        return loop.run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
