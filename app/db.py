"""SQLite persistence layer for the Task Organizer app.

Uses the Python standard-library ``sqlite3`` module directly (no ORM) so the
app has one fewer dependency to install and the on-disk file stays a plain,
inspectable SQLite database -- handy since that same file is what gets
pointed at a OneDrive-synced folder for the "mobile sync" story (see
sync.py and the README).

All functions in this module take an explicit ``db_path`` (or a connection)
so tests can point at a temporary file instead of the user's real database.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, List, Optional

from app.models import (
    STATUS_DONE,
    Task,
    TimeEntry,
)

DEFAULT_DB_FILENAME = "task_organizer.db"


def default_db_path() -> str:
    """Where the database lives if the user hasn't configured a custom path.

    Defaults to a folder in the user's home directory. Users who want mobile
    sync should change this (via Settings) to a path inside their OneDrive
    folder -- see sync.py.
    """
    home = os.path.expanduser("~")
    app_dir = os.path.join(home, ".task_organizer")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, DEFAULT_DB_FILENAME)


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    project TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    quadrant TEXT NOT NULL DEFAULT 'not_urgent_important',
    deadline TEXT,
    estimate_minutes INTEGER NOT NULL DEFAULT 0,
    actual_minutes INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'todo',
    timer_started_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS time_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    stopped_at TEXT,
    minutes INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_quadrant ON tasks(quadrant);
CREATE INDEX IF NOT EXISTS idx_time_entries_task ON time_entries(task_id);
"""


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or default_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Create tables if they don't already exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def connect(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """Context manager yielding a connection with the schema ensured."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        source=row["source"],
        project=row["project"],
        tags=json.loads(row["tags"] or "[]"),
        quadrant=row["quadrant"],
        deadline=row["deadline"],
        estimate_minutes=row["estimate_minutes"],
        actual_minutes=row["actual_minutes"],
        status=row["status"],
        timer_started_at=row["timer_started_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_task(task: Task, db_path: Optional[str] = None) -> Task:
    now = datetime.now().isoformat(timespec="seconds")
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks
                (title, description, source, project, tags, quadrant, deadline,
                 estimate_minutes, actual_minutes, status, timer_started_at,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.title,
                task.description,
                task.source,
                task.project,
                json.dumps(task.tags or []),
                task.quadrant,
                task.deadline,
                task.estimate_minutes,
                task.actual_minutes,
                task.status,
                task.timer_started_at,
                now,
                now,
            ),
        )
        task.id = cur.lastrowid
        task.created_at = now
        task.updated_at = now
    return task


def get_task(task_id: int, db_path: Optional[str] = None) -> Optional[Task]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None


def list_tasks(
    db_path: Optional[str] = None,
    status: Optional[str] = None,
    quadrant: Optional[str] = None,
    project: Optional[str] = None,
) -> List[Task]:
    query = "SELECT * FROM tasks WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if quadrant:
        query += " AND quadrant = ?"
        params.append(quadrant)
    if project:
        query += " AND project = ?"
        params.append(project)
    query += " ORDER BY (deadline IS NULL), deadline ASC, id DESC"
    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_task(r) for r in rows]


def update_task(task: Task, db_path: Optional[str] = None) -> Task:
    if task.id is None:
        raise ValueError("Cannot update a task with no id -- call create_task first.")
    task.updated_at = datetime.now().isoformat(timespec="seconds")
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE tasks SET
                title = ?, description = ?, source = ?, project = ?, tags = ?,
                quadrant = ?, deadline = ?, estimate_minutes = ?, actual_minutes = ?,
                status = ?, timer_started_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                task.title,
                task.description,
                task.source,
                task.project,
                json.dumps(task.tags or []),
                task.quadrant,
                task.deadline,
                task.estimate_minutes,
                task.actual_minutes,
                task.status,
                task.timer_started_at,
                task.updated_at,
                task.id,
            ),
        )
    return task


def delete_task(task_id: int, db_path: Optional[str] = None) -> None:
    with connect(db_path) as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def mark_done(task_id: int, db_path: Optional[str] = None) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (STATUS_DONE, datetime.now().isoformat(timespec="seconds"), task_id),
        )


# ---------------------------------------------------------------------------
# Time tracking
# ---------------------------------------------------------------------------

def start_timer(task_id: int, db_path: Optional[str] = None) -> str:
    """Mark a task's timer as running. Returns the ISO start timestamp."""
    started_at = datetime.now().isoformat(timespec="seconds")
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT timer_started_at FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"No task with id {task_id}")
        if row["timer_started_at"]:
            # Already running; treat as idempotent and return existing start.
            return row["timer_started_at"]
        conn.execute(
            "UPDATE tasks SET timer_started_at = ?, updated_at = ? WHERE id = ?",
            (started_at, started_at, task_id),
        )
        conn.execute(
            "INSERT INTO time_entries (task_id, started_at, stopped_at, minutes) "
            "VALUES (?, ?, NULL, 0)",
            (task_id, started_at),
        )
    return started_at


def stop_timer(task_id: int, db_path: Optional[str] = None) -> int:
    """Stop a running timer, accumulate elapsed minutes onto the task.

    Returns the number of minutes recorded for this session (>= 0).
    """
    stopped_at_dt = datetime.now()
    stopped_at = stopped_at_dt.isoformat(timespec="seconds")
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT timer_started_at, actual_minutes FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"No task with id {task_id}")
        if not row["timer_started_at"]:
            return 0  # Timer wasn't running; nothing to do.

        started_at_dt = datetime.fromisoformat(row["timer_started_at"])
        elapsed_minutes = max(0, round((stopped_at_dt - started_at_dt).total_seconds() / 60))

        new_actual = row["actual_minutes"] + elapsed_minutes
        conn.execute(
            "UPDATE tasks SET timer_started_at = NULL, actual_minutes = ?, updated_at = ? "
            "WHERE id = ?",
            (new_actual, stopped_at, task_id),
        )
        conn.execute(
            """
            UPDATE time_entries SET stopped_at = ?, minutes = ?
            WHERE task_id = ? AND stopped_at IS NULL
            """,
            (stopped_at, elapsed_minutes, task_id),
        )
    return elapsed_minutes


def list_time_entries(
    db_path: Optional[str] = None, since: Optional[str] = None
) -> List[TimeEntry]:
    query = "SELECT * FROM time_entries WHERE stopped_at IS NOT NULL"
    params: list = []
    if since:
        query += " AND started_at >= ?"
        params.append(since)
    query += " ORDER BY started_at DESC"
    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [
            TimeEntry(
                id=r["id"],
                task_id=r["task_id"],
                started_at=r["started_at"],
                stopped_at=r["stopped_at"],
                minutes=r["minutes"],
            )
            for r in rows
        ]
