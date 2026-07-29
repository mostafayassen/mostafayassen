"""Smoke tests for the PySide6 UI layer.

Full GUI testing (simulating clicks, drag-and-drop between Eisenhower
quadrants, etc.) is intentionally NOT attempted here: it requires a real
Qt event loop and, on Linux, either a display or the "offscreen" Qt
platform plugin with all its native shared-library dependencies (libGL,
libxkbcommon, fontconfig, etc.) available -- which is not guaranteed in a
minimal/headless CI or sandbox container, and is out of scope for this
project's test suite per its design (core task engine + integrations are
what's unit-tested; the UI is manually verified by running the app on
Windows, its target platform).

This file does the cheapest useful thing instead: it verifies the UI
modules at least *import* cleanly (i.e. no syntax errors, no missing
symbols) and, if a working Qt "offscreen" platform is available in this
environment, goes one step further and instantiates the main window
against a temporary database. If Qt can't initialize here, every test
below skips itself with an explanation rather than failing the whole
suite or silently vanishing.
"""

from __future__ import annotations

import os

import pytest


def _qt_offscreen_available() -> bool:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        return True
    except Exception:
        return False


QT_OK = _qt_offscreen_available()


def test_ui_modules_import():
    """All UI modules should import without error -- this alone catches
    typos, bad imports, and syntax errors even when a Qt display isn't
    available to actually instantiate widgets."""
    import app.ui.dashboard  # noqa: F401
    import app.ui.main_window  # noqa: F401
    import app.ui.matrix_view  # noqa: F401
    import app.ui.reports_view  # noqa: F401
    import app.ui.settings_view  # noqa: F401
    import app.ui.task_dialog  # noqa: F401
    import app.ui.time_tracker  # noqa: F401


@pytest.mark.skipif(not QT_OK, reason="No usable Qt platform plugin (offscreen) in this sandbox.")
def test_main_window_constructs(tmp_path):
    from app.config import AppConfig
    from app.ui.main_window import MainWindow

    config = AppConfig(db_path=str(tmp_path / "smoke.db"))
    window = MainWindow(db_path=config.db_path, config=config)
    assert window.windowTitle() == "Task Organizer"
    window.close()


@pytest.mark.skipif(not QT_OK, reason="No usable Qt platform plugin (offscreen) in this sandbox.")
def test_dashboard_view_constructs(tmp_path):
    from app import db
    from app.ui.dashboard import DashboardView

    db_path = str(tmp_path / "smoke_dash.db")
    db.init_db(db_path)
    view = DashboardView(db_path)
    assert view is not None
