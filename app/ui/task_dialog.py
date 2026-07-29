"""Add/edit task dialog."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.models import ALL_QUADRANTS, ALL_STATUSES, QUADRANT_LABELS, Task


class TaskDialog(QDialog):
    """Modal dialog for creating or editing a Task.

    Usage:
        dialog = TaskDialog(parent, task=existing_task_or_None)
        if dialog.exec() == QDialog.Accepted:
            task = dialog.result_task()
    """

    def __init__(self, parent=None, task: Optional[Task] = None, ai_provider=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Task" if task else "New Task")
        self.setMinimumWidth(420)
        self._task = task or Task()
        self._ai_provider = ai_provider

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit(self._task.title)
        form.addRow("Title*", self.title_edit)

        self.description_edit = QPlainTextEdit(self._task.description)
        self.description_edit.setFixedHeight(80)
        form.addRow("Description", self.description_edit)

        self.project_edit = QLineEdit(self._task.project)
        form.addRow("Project", self.project_edit)

        self.tags_edit = QLineEdit(", ".join(self._task.tags))
        self.tags_edit.setPlaceholderText("comma, separated, tags")
        form.addRow("Tags", self.tags_edit)

        self.quadrant_combo = QComboBox()
        for q in ALL_QUADRANTS:
            self.quadrant_combo.addItem(QUADRANT_LABELS[q], q)
        idx = ALL_QUADRANTS.index(self._task.quadrant) if self._task.quadrant in ALL_QUADRANTS else 1
        self.quadrant_combo.setCurrentIndex(idx)
        form.addRow("Priority (Eisenhower)", self.quadrant_combo)

        if self._ai_provider is not None:
            suggest_btn = QPushButton("Suggest with AI")
            suggest_btn.clicked.connect(self._suggest_quadrant)
            form.addRow("", suggest_btn)

        self.deadline_check_edit = QDateTimeEdit()
        self.deadline_check_edit.setCalendarPopup(True)
        self.deadline_check_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        if self._task.deadline:
            try:
                dt = datetime.fromisoformat(self._task.deadline)
                self.deadline_check_edit.setDateTime(QDateTime(dt))
            except ValueError:
                self.deadline_check_edit.setDateTime(QDateTime.currentDateTime().addDays(1))
        else:
            self.deadline_check_edit.setDateTime(QDateTime.currentDateTime().addDays(1))
        form.addRow("Deadline", self.deadline_check_edit)

        self.no_deadline_checkbox = QComboBox()
        self.no_deadline_checkbox.addItems(["Has deadline", "No deadline"])
        self.no_deadline_checkbox.setCurrentIndex(1 if not self._task.deadline else 0)
        form.addRow("", self.no_deadline_checkbox)

        self.estimate_spin = QSpinBox()
        self.estimate_spin.setRange(0, 100000)
        self.estimate_spin.setSuffix(" min")
        self.estimate_spin.setValue(self._task.estimate_minutes)
        form.addRow("Estimated time", self.estimate_spin)

        self.status_combo = QComboBox()
        self.status_combo.addItems(ALL_STATUSES)
        if self._task.status in ALL_STATUSES:
            self.status_combo.setCurrentText(self._task.status)
        form.addRow("Status", self.status_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _suggest_quadrant(self) -> None:
        if self._ai_provider is None:
            return
        result = self._ai_provider.suggest_quadrant(
            self.title_edit.text(), self.description_edit.toPlainText()
        )
        if not result.ok:
            QMessageBox.information(self, "AI suggestion unavailable", result.error or "Unknown error")
            return
        if result.text in ALL_QUADRANTS:
            self.quadrant_combo.setCurrentIndex(ALL_QUADRANTS.index(result.text))

    def _on_accept(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Title required", "Please enter a task title.")
            return
        self.accept()

    def result_task(self) -> Task:
        task = self._task
        task.title = self.title_edit.text().strip()
        task.description = self.description_edit.toPlainText()
        task.project = self.project_edit.text().strip()
        task.tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        task.quadrant = self.quadrant_combo.currentData()
        if self.no_deadline_checkbox.currentIndex() == 1:
            task.deadline = None
        else:
            task.deadline = self.deadline_check_edit.dateTime().toPython().isoformat(timespec="seconds")
        task.estimate_minutes = self.estimate_spin.value()
        task.status = self.status_combo.currentText()
        return task
