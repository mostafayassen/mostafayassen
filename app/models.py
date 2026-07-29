"""Data model definitions for the Task Organizer app.

These are plain dataclasses used as an in-memory representation of rows
stored in SQLite (see db.py). Keeping them separate from the persistence
code makes it easy to pass task objects around the UI layer without
leaking SQL details everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

# Eisenhower matrix quadrants.
QUADRANT_URGENT_IMPORTANT = "urgent_important"        # Do first
QUADRANT_NOT_URGENT_IMPORTANT = "not_urgent_important"  # Schedule
QUADRANT_URGENT_NOT_IMPORTANT = "urgent_not_important"  # Delegate
QUADRANT_NOT_URGENT_NOT_IMPORTANT = "not_urgent_not_important"  # Eliminate

ALL_QUADRANTS = [
    QUADRANT_URGENT_IMPORTANT,
    QUADRANT_NOT_URGENT_IMPORTANT,
    QUADRANT_URGENT_NOT_IMPORTANT,
    QUADRANT_NOT_URGENT_NOT_IMPORTANT,
]

QUADRANT_LABELS = {
    QUADRANT_URGENT_IMPORTANT: "Urgent & Important (Do First)",
    QUADRANT_NOT_URGENT_IMPORTANT: "Not Urgent & Important (Schedule)",
    QUADRANT_URGENT_NOT_IMPORTANT: "Urgent & Not Important (Delegate)",
    QUADRANT_NOT_URGENT_NOT_IMPORTANT: "Not Urgent & Not Important (Eliminate)",
}

STATUS_TODO = "todo"
STATUS_IN_PROGRESS = "in_progress"
STATUS_DONE = "done"

ALL_STATUSES = [STATUS_TODO, STATUS_IN_PROGRESS, STATUS_DONE]

SOURCE_MANUAL = "manual"
SOURCE_EMAIL = "email"
SOURCE_TEAMS = "teams"
SOURCE_EXCEL = "excel"


@dataclass
class Task:
    """Represents a single task/to-do item."""

    id: Optional[int] = None
    title: str = ""
    description: str = ""
    source: str = SOURCE_MANUAL
    project: str = ""
    tags: List[str] = field(default_factory=list)
    quadrant: str = QUADRANT_NOT_URGENT_IMPORTANT
    deadline: Optional[str] = None  # ISO 8601 string, e.g. "2026-08-01T17:00:00"
    estimate_minutes: int = 0
    actual_minutes: int = 0
    status: str = STATUS_TODO
    timer_started_at: Optional[str] = None  # ISO 8601 string, set while timer running
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def tags_display(self) -> str:
        return ", ".join(self.tags)

    @property
    def is_timer_running(self) -> bool:
        return bool(self.timer_started_at)

    @property
    def is_overdue(self) -> bool:
        if not self.deadline or self.status == STATUS_DONE:
            return False
        try:
            deadline_dt = datetime.fromisoformat(self.deadline)
        except ValueError:
            return False
        return deadline_dt < datetime.now()


@dataclass
class TimeEntry:
    """A single start/stop time-tracking session logged against a task."""

    id: Optional[int] = None
    task_id: int = 0
    started_at: str = ""
    stopped_at: Optional[str] = None
    minutes: int = 0
