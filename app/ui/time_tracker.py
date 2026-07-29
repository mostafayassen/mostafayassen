"""Time tracker view: start/stop timer per task, accumulates actual_minutes."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import db
from app.models import STATUS_DONE, STATUS_IN_PROGRESS, Task

COLUMNS = ["Title", "Project", "Estimate (min)", "Actual (min)", "Status", "Timer"]


class TimeTrackerView(QWidget):
    def __init__(self, db_path: Optional[str], parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self._tasks: list[Task] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Time Tracker</h2>"))
        layout.addWidget(
            QLabel("Start a timer while you work on a task; stop it when you're done.")
        )

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start timer")
        self.start_btn.clicked.connect(self._start_selected)
        self.stop_btn = QPushButton("Stop timer")
        self.stop_btn.clicked.connect(self._stop_selected)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(refresh_btn)
        layout.addLayout(btn_row)

        # Refresh the "running" elapsed display every 30s without hitting
        # the DB for a full reload -- keep it simple and just re-query.
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(30_000)
        self._tick_timer.timeout.connect(self.refresh)
        self._tick_timer.start()

        self.refresh()

    def refresh(self) -> None:
        self._tasks = [t for t in db.list_tasks(self.db_path) if t.status != STATUS_DONE]
        self.table.setRowCount(len(self._tasks))
        for row, task in enumerate(self._tasks):
            self.table.setItem(row, 0, QTableWidgetItem(task.title))
            self.table.setItem(row, 1, QTableWidgetItem(task.project))
            self.table.setItem(row, 2, QTableWidgetItem(str(task.estimate_minutes)))
            self.table.setItem(row, 3, QTableWidgetItem(str(task.actual_minutes)))
            self.table.setItem(row, 4, QTableWidgetItem(task.status))
            timer_text = "Running" if task.is_timer_running else "Stopped"
            self.table.setItem(row, 5, QTableWidgetItem(timer_text))
            self.table.item(row, 0).setData(Qt.UserRole, task.id)

    def _selected_task(self) -> Optional[Task]:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._tasks):
            return None
        return self._tasks[row]

    def _start_selected(self) -> None:
        task = self._selected_task()
        if not task:
            QMessageBox.information(self, "No task selected", "Select a task first.")
            return
        db.start_timer(task.id, self.db_path)
        if task.status not in (STATUS_IN_PROGRESS,):
            task.status = STATUS_IN_PROGRESS
            db.update_task(task, self.db_path)
        self.refresh()

    def _stop_selected(self) -> None:
        task = self._selected_task()
        if not task:
            QMessageBox.information(self, "No task selected", "Select a task first.")
            return
        minutes = db.stop_timer(task.id, self.db_path)
        self.refresh()
        if minutes:
            QMessageBox.information(self, "Timer stopped", f"Logged {minutes} minute(s).")
