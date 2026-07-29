"""Application entrypoint.

Run with:
    python main.py
(from the repo root -- see README.md for full setup instructions.)
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from app.config import load_config
from app.notifications import NotificationScheduler
from app.ui.main_window import MainWindow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Task Organizer")

    config = load_config()
    window = MainWindow(db_path=config.db_path, config=config)

    scheduler = None
    try:
        def in_app_fallback(title: str, message: str) -> None:
            window.statusBar().showMessage(f"{title}: {message}", 10_000)

        scheduler = NotificationScheduler(
            db_path=config.db_path,
            in_app_fallback=in_app_fallback,
        )
        scheduler.start()
    except Exception as exc:  # noqa: BLE001 - notifications must never block startup
        logger.warning("Could not start notification scheduler: %s", exc)

    window.show()
    exit_code = app.exec()

    if scheduler is not None:
        scheduler.shutdown()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
