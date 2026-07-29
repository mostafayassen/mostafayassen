"""Unit tests for app/db.py -- task CRUD and time tracking.

These tests use a temporary SQLite file per test (via pytest's tmp_path
fixture) so they never touch the user's real database, and don't require
any network, Windows-only library, or GUI event loop.
"""

from __future__ import annotations

import os
import time

import pytest

from app import db
from app.models import (
    QUADRANT_URGENT_IMPORTANT,
    STATUS_DONE,
    STATUS_TODO,
    Task,
)


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "test_tasks.db")


def test_init_db_creates_file(db_path):
    db.init_db(db_path)
    assert os.path.exists(db_path)


def test_create_and_get_task(db_path):
    task = Task(title="Write report", project="Alpha", tags=["writing", "urgent"])
    created = db.create_task(task, db_path)

    assert created.id is not None
    assert created.created_at is not None

    fetched = db.get_task(created.id, db_path)
    assert fetched is not None
    assert fetched.title == "Write report"
    assert fetched.project == "Alpha"
    assert fetched.tags == ["writing", "urgent"]
    assert fetched.status == STATUS_TODO


def test_list_tasks_filters(db_path):
    db.create_task(Task(title="A", status=STATUS_TODO, quadrant=QUADRANT_URGENT_IMPORTANT), db_path)
    db.create_task(Task(title="B", status=STATUS_DONE), db_path)

    all_tasks = db.list_tasks(db_path)
    assert len(all_tasks) == 2

    todo_only = db.list_tasks(db_path, status=STATUS_TODO)
    assert len(todo_only) == 1
    assert todo_only[0].title == "A"

    urgent_only = db.list_tasks(db_path, quadrant=QUADRANT_URGENT_IMPORTANT)
    assert len(urgent_only) == 1
    assert urgent_only[0].title == "A"


def test_update_task(db_path):
    created = db.create_task(Task(title="Original"), db_path)
    created.title = "Updated"
    created.status = STATUS_DONE
    db.update_task(created, db_path)

    fetched = db.get_task(created.id, db_path)
    assert fetched.title == "Updated"
    assert fetched.status == STATUS_DONE


def test_update_task_without_id_raises(db_path):
    task = Task(title="No id yet")
    with pytest.raises(ValueError):
        db.update_task(task, db_path)


def test_delete_task(db_path):
    created = db.create_task(Task(title="Delete me"), db_path)
    db.delete_task(created.id, db_path)
    assert db.get_task(created.id, db_path) is None


def test_mark_done(db_path):
    created = db.create_task(Task(title="Finish me"), db_path)
    db.mark_done(created.id, db_path)
    fetched = db.get_task(created.id, db_path)
    assert fetched.status == STATUS_DONE


def test_start_and_stop_timer_accumulates_minutes(db_path):
    created = db.create_task(Task(title="Timed task"), db_path)

    started_at = db.start_timer(created.id, db_path)
    assert started_at

    running_task = db.get_task(created.id, db_path)
    assert running_task.is_timer_running

    # Timer is idempotent: starting again while already running is a no-op.
    same_start = db.start_timer(created.id, db_path)
    assert same_start == started_at

    time.sleep(1)
    minutes = db.stop_timer(created.id, db_path)
    assert minutes >= 0

    stopped_task = db.get_task(created.id, db_path)
    assert not stopped_task.is_timer_running
    assert stopped_task.actual_minutes == minutes

    entries = db.list_time_entries(db_path)
    assert len(entries) == 1
    assert entries[0].task_id == created.id


def test_stop_timer_when_not_running_is_noop(db_path):
    created = db.create_task(Task(title="Never started"), db_path)
    minutes = db.stop_timer(created.id, db_path)
    assert minutes == 0


def test_task_is_overdue_property():
    from datetime import datetime, timedelta

    past = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    future = (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds")

    overdue_task = Task(title="Late", deadline=past, status=STATUS_TODO)
    assert overdue_task.is_overdue

    future_task = Task(title="Not yet", deadline=future, status=STATUS_TODO)
    assert not future_task.is_overdue

    done_task = Task(title="Done but late", deadline=past, status=STATUS_DONE)
    assert not done_task.is_overdue
