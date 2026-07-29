"""Main application window: navigation between Dashboard / Matrix /
Time Tracker / Reports / Settings, plus the menu bar actions for
task CRUD, Excel import/export, and Outlook import.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QWidget,
)

from app import db
from app.config import AppConfig, load_config
from app.integrations import excel_io
from app.integrations.ai_provider import get_default_provider
from app.models import Task
from app.ui.dashboard import DashboardView
from app.ui.matrix_view import MatrixView
from app.ui.reports_view import ReportsView
from app.ui.settings_view import SettingsView
from app.ui.task_dialog import TaskDialog
from app.ui.time_tracker import TimeTrackerView

logger = logging.getLogger(__name__)

NAV_ITEMS = ["Dashboard", "Matrix", "Time Tracker", "Reports", "Settings"]


class MainWindow(QMainWindow):
    def __init__(self, db_path: Optional[str] = None, config: Optional[AppConfig] = None):
        super().__init__()
        self.setWindowTitle("Task Organizer")
        self.resize(1100, 700)

        self.config = config or load_config()
        self.db_path = db_path or self.config.db_path
        db.init_db(self.db_path)

        self.ai_provider = get_default_provider(
            host=self.config.ollama_host, model=self.config.ollama_model
        )

        self._build_ui()
        self._build_toolbar()
        self.setStatusBar(QStatusBar())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Horizontal)

        self.nav_list = QListWidget()
        self.nav_list.addItems(NAV_ITEMS)
        self.nav_list.setMaximumWidth(160)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        splitter.addWidget(self.nav_list)

        self.stack = QStackedWidget()

        self.dashboard_view = DashboardView(self.db_path, on_open_task=self.open_task_editor)
        self.matrix_view = MatrixView(self.db_path, on_open_task=self.open_task_editor)
        self.time_tracker_view = TimeTrackerView(self.db_path)
        self.reports_view = ReportsView(self.db_path)
        self.settings_view = SettingsView(on_config_changed=self._on_config_changed)

        for view in (
            self.dashboard_view,
            self.matrix_view,
            self.time_tracker_view,
            self.reports_view,
            self.settings_view,
        ):
            self.stack.addWidget(view)

        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)
        self.nav_list.setCurrentRow(0)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)

        new_task_action = toolbar.addAction("New Task")
        new_task_action.triggered.connect(self.new_task)

        import_action = toolbar.addAction("Import from Excel")
        import_action.triggered.connect(self.import_from_excel)

        export_action = toolbar.addAction("Export to Excel")
        export_action.triggered.connect(self.export_to_excel)

        outlook_action = toolbar.addAction("Import from Outlook")
        outlook_action.triggered.connect(self.import_from_outlook)

        refresh_action = toolbar.addAction("Refresh All")
        refresh_action.triggered.connect(self.refresh_all)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _on_nav_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        self.refresh_all()

    def _on_config_changed(self, config: AppConfig) -> None:
        self.config = config
        self.ai_provider = get_default_provider(host=config.ollama_host, model=config.ollama_model)

    # ------------------------------------------------------------------
    # Task actions
    # ------------------------------------------------------------------
    def new_task(self) -> None:
        dialog = TaskDialog(self, ai_provider=self.ai_provider)
        if dialog.exec():
            task = dialog.result_task()
            db.create_task(task, self.db_path)
            self.refresh_all()

    def open_task_editor(self, task_id: int) -> None:
        task = db.get_task(task_id, self.db_path)
        if task is None:
            return
        dialog = TaskDialog(self, task=task, ai_provider=self.ai_provider)
        if dialog.exec():
            updated = dialog.result_task()
            db.update_task(updated, self.db_path)
            self.refresh_all()

    def refresh_all(self) -> None:
        self.dashboard_view.refresh()
        self.matrix_view.refresh()
        self.time_tracker_view.refresh()
        self.reports_view.refresh()

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------
    def import_from_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import tasks", "", "Excel Files (*.xlsx)")
        if not path:
            return
        try:
            tasks = excel_io.import_tasks_from_xlsx(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        for task in tasks:
            db.create_task(task, self.db_path)
        QMessageBox.information(self, "Imported", f"Imported {len(tasks)} task(s).")
        self.refresh_all()

    def export_to_excel(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export tasks", "tasks.xlsx", "Excel Files (*.xlsx)")
        if not path:
            return
        tasks = db.list_tasks(self.db_path)
        try:
            excel_io.export_tasks_to_xlsx(tasks, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Exported", f"Exported {len(tasks)} task(s) to {path}")

    # ------------------------------------------------------------------
    # Outlook
    # ------------------------------------------------------------------
    def import_from_outlook(self) -> None:
        from app.integrations import outlook_graph

        client_id = self.config.azure_client_id
        if not client_id:
            QMessageBox.information(
                self,
                "Azure app not configured",
                "Go to Settings and paste your Azure AD Application (client) "
                "ID first. See README.md 'Outlook & Teams setup'.",
            )
            return

        def on_code(message: str) -> None:
            QMessageBox.information(self, "Sign in to Microsoft", message)

        try:
            result = outlook_graph.acquire_token_device_flow(
                client_id, outlook_graph.MAIL_SCOPES, on_code
            )
        except outlook_graph.GraphAuthError as exc:
            QMessageBox.critical(self, "Sign-in failed", str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - never crash on network issues
            QMessageBox.critical(self, "Sign-in failed", str(exc))
            return

        try:
            emails = outlook_graph.list_recent_emails(result["access_token"])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Could not fetch emails", str(exc))
            return

        if not emails:
            QMessageBox.information(self, "No emails", "No recent emails found.")
            return

        subjects = [f"{e.subject}  —  {e.sender}" for e in emails]
        choice, ok = QInputDialog.getItem(
            self, "Convert email to task", "Choose an email:", subjects, editable=False
        )
        if not ok:
            return
        email = emails[subjects.index(choice)]
        fields = outlook_graph.email_to_task_fields(email)
        task = Task(**fields)
        dialog = TaskDialog(self, task=task, ai_provider=self.ai_provider)
        if dialog.exec():
            db.create_task(dialog.result_task(), self.db_path)
            self.refresh_all()
