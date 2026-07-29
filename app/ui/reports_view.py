"""Weekly productivity report: time by project, completed vs planned,
overdue tasks. The report-building logic (``build_weekly_report``) is a
plain function with no Qt dependency so it's independently unit-testable;
the QWidget below just renders it and offers an "Export to Excel" button.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app import db
from app.integrations.excel_io import export_report_to_xlsx
from app.models import STATUS_DONE, Task


def build_weekly_report(db_path: Optional[str], days: int = 7) -> dict:
    """Returns a dict with:
      summary: {metric label -> value}
      time_by_project: {project -> minutes}
      overdue_tasks: [Task, ...]
      completed_tasks: [Task, ...]
      planned_tasks: [Task, ...]  (tasks with a deadline in the period)
    """
    since_dt = datetime.now() - timedelta(days=days)
    since = since_dt.isoformat(timespec="seconds")

    tasks = db.list_tasks(db_path=db_path)
    entries = db.list_time_entries(db_path=db_path, since=since)

    time_by_project: dict = defaultdict(int)
    task_by_id = {t.id: t for t in tasks}
    for entry in entries:
        task = task_by_id.get(entry.task_id)
        project = task.project if task else ""
        time_by_project[project] += entry.minutes

    completed_tasks = [
        t for t in tasks if t.status == STATUS_DONE and t.updated_at and t.updated_at >= since
    ]
    planned_tasks = [
        t for t in tasks if t.deadline and since_dt <= _safe_parse(t.deadline, since_dt)
    ]
    overdue_tasks = [t for t in tasks if t.is_overdue]

    total_minutes = sum(time_by_project.values())

    summary = {
        "Period (days)": days,
        "Total time logged (minutes)": total_minutes,
        "Total time logged (hours)": round(total_minutes / 60, 2),
        "Tasks completed": len(completed_tasks),
        "Tasks planned (had a deadline)": len(planned_tasks),
        "Tasks overdue (as of now)": len(overdue_tasks),
    }

    return {
        "summary": summary,
        "time_by_project": dict(time_by_project),
        "overdue_tasks": overdue_tasks,
        "completed_tasks": completed_tasks,
        "planned_tasks": planned_tasks,
    }


def _safe_parse(value: str, fallback: datetime) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return fallback


class ReportsView(QWidget):
    def __init__(self, db_path: Optional[str], parent=None):
        super().__init__(parent)
        self.db_path = db_path

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Weekly Report</h2>"))

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

        export_btn = QPushButton("Export report to Excel")
        export_btn.clicked.connect(self._export)
        layout.addWidget(export_btn)

        self._last_report: dict = {}
        self.refresh()

    def refresh(self) -> None:
        self._last_report = build_weekly_report(self.db_path)
        lines = ["<b>Summary</b><ul>"]
        for k, v in self._last_report["summary"].items():
            lines.append(f"<li>{k}: {v}</li>")
        lines.append("</ul><b>Time by project</b><ul>")
        for project, minutes in self._last_report["time_by_project"].items():
            lines.append(f"<li>{project or '(no project)'}: {minutes} min</li>")
        lines.append("</ul><b>Overdue tasks</b><ul>")
        for t in self._last_report["overdue_tasks"]:
            lines.append(f"<li>{t.title} (was due {t.deadline})</li>")
        lines.append("</ul>")
        self.text_area.setHtml("".join(lines))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export report", "weekly_report.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return
        try:
            export_report_to_xlsx(self._last_report, path)
            QMessageBox.information(self, "Exported", f"Report saved to {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))
