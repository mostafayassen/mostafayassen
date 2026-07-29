"""Dashboard: today's tasks + upcoming deadlines at a glance."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import db
from app.models import STATUS_DONE, Task


class DashboardView(QWidget):
    def __init__(self, db_path: Optional[str], on_open_task=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.on_open_task = on_open_task

        layout = QVBoxLayout(self)

        header = QLabel("<h2>Dashboard</h2>")
        layout.addWidget(header)

        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)

        row = QHBoxLayout()

        today_box = QGroupBox("Today's tasks")
        today_layout = QVBoxLayout(today_box)
        self.today_list = QListWidget()
        self.today_list.itemDoubleClicked.connect(self._open_selected_today)
        today_layout.addWidget(self.today_list)
        row.addWidget(today_box)

        upcoming_box = QGroupBox("Upcoming deadlines (next 7 days)")
        upcoming_layout = QVBoxLayout(upcoming_box)
        self.upcoming_list = QListWidget()
        self.upcoming_list.itemDoubleClicked.connect(self._open_selected_upcoming)
        upcoming_layout.addWidget(self.upcoming_list)
        row.addWidget(upcoming_box)

        overdue_box = QGroupBox("Overdue")
        overdue_layout = QVBoxLayout(overdue_box)
        self.overdue_list = QListWidget()
        self.overdue_list.itemDoubleClicked.connect(self._open_selected_overdue)
        overdue_layout.addWidget(self.overdue_list)
        row.addWidget(overdue_box)

        layout.addLayout(row)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

        self._today_tasks = []
        self._upcoming_tasks = []
        self._overdue_tasks = []

        self.refresh()

    def refresh(self) -> None:
        tasks = [t for t in db.list_tasks(self.db_path) if t.status != STATUS_DONE]
        now = datetime.now()
        today_end = now.replace(hour=23, minute=59, second=59)
        week_end = now + timedelta(days=7)

        self._today_tasks = []
        self._upcoming_tasks = []
        self._overdue_tasks = []

        for t in tasks:
            if t.is_overdue:
                self._overdue_tasks.append(t)
                continue
            if not t.deadline:
                continue
            try:
                deadline_dt = datetime.fromisoformat(t.deadline)
            except ValueError:
                continue
            if deadline_dt <= today_end:
                self._today_tasks.append(t)
            elif deadline_dt <= week_end:
                self._upcoming_tasks.append(t)

        self.today_list.clear()
        for t in self._today_tasks:
            self.today_list.addItem(self._make_item(t))

        self.upcoming_list.clear()
        for t in self._upcoming_tasks:
            self.upcoming_list.addItem(self._make_item(t))

        self.overdue_list.clear()
        for t in self._overdue_tasks:
            self.overdue_list.addItem(self._make_item(t))

        total_open = len(tasks)
        self.summary_label.setText(
            f"{total_open} open task(s) — {len(self._overdue_tasks)} overdue, "
            f"{len(self._today_tasks)} due today, {len(self._upcoming_tasks)} due this week."
        )

    @staticmethod
    def _make_item(task: Task) -> QListWidgetItem:
        label = f"{task.title}"
        if task.deadline:
            label += f"  (due {task.deadline})"
        if task.project:
            label += f"  [{task.project}]"
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, task.id)
        return item

    def _open_selected_today(self, item: QListWidgetItem) -> None:
        self._emit_open(item, self._today_tasks)

    def _open_selected_upcoming(self, item: QListWidgetItem) -> None:
        self._emit_open(item, self._upcoming_tasks)

    def _open_selected_overdue(self, item: QListWidgetItem) -> None:
        self._emit_open(item, self._overdue_tasks)

    def _emit_open(self, item: QListWidgetItem, task_list) -> None:
        task_id = item.data(Qt.UserRole)
        if self.on_open_task:
            self.on_open_task(task_id)
