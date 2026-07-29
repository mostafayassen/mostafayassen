"""Reminders & notifications: instant deadline alerts + daily/weekly digests.

Uses APScheduler's BackgroundScheduler to run periodic checks. Actual
notification delivery tries a Windows toast library first (``plyer``, which
wraps ``win10toast``/native APIs), and falls back to an in-app callback
(e.g. a status-bar banner) if that's unavailable -- which is always the
case on non-Windows systems, and is expected/fine there. Every import and
call into a Windows-only library is wrapped in try/except so the rest of
the app (and the test suite, run on Linux) keeps working.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app import db
from app.models import STATUS_DONE, Task

logger = logging.getLogger(__name__)

# In-app fallback banner callback signature: (title: str, message: str) -> None
InAppNotifier = Callable[[str, str], None]

try:
    from plyer import notification as _plyer_notification  # type: ignore
    _PLYER_AVAILABLE = True
except Exception:  # pragma: no cover - platform dependent
    _plyer_notification = None
    _PLYER_AVAILABLE = False


def send_notification(title: str, message: str, in_app_fallback: Optional[InAppNotifier] = None) -> None:
    """Best-effort desktop toast; falls back to an in-app callback, then to
    a log line. Never raises."""
    if _PLYER_AVAILABLE:
        try:
            _plyer_notification.notify(title=title, message=message, timeout=10)
            return
        except Exception as exc:  # pragma: no cover - platform dependent
            logger.info("Toast notification failed, falling back: %s", exc)

    if in_app_fallback is not None:
        try:
            in_app_fallback(title, message)
            return
        except Exception as exc:
            logger.warning("In-app notification fallback failed: %s", exc)

    logger.info("[notification] %s: %s", title, message)


def upcoming_deadline_tasks(db_path: Optional[str], within_hours: int = 24) -> List[Task]:
    """Tasks with a deadline within the next `within_hours` that aren't done."""
    now = datetime.now()
    cutoff = now + timedelta(hours=within_hours)
    tasks = db.list_tasks(db_path=db_path)
    result = []
    for t in tasks:
        if t.status == STATUS_DONE or not t.deadline:
            continue
        try:
            deadline_dt = datetime.fromisoformat(t.deadline)
        except ValueError:
            continue
        if now <= deadline_dt <= cutoff:
            result.append(t)
    return result


def overdue_tasks(db_path: Optional[str]) -> List[Task]:
    tasks = db.list_tasks(db_path=db_path)
    return [t for t in tasks if t.is_overdue]


def build_daily_digest_text(db_path: Optional[str]) -> str:
    upcoming = upcoming_deadline_tasks(db_path, within_hours=24)
    overdue = overdue_tasks(db_path)
    lines = []
    if overdue:
        lines.append(f"{len(overdue)} task(s) overdue.")
    if upcoming:
        lines.append(f"{len(upcoming)} task(s) due in the next 24 hours.")
    if not lines:
        lines.append("Nothing urgent today. Nice work staying on top of things.")
    return " ".join(lines)


def build_weekly_digest_text(db_path: Optional[str]) -> str:
    since = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    entries = db.list_time_entries(db_path, since=since)
    total_minutes = sum(e.minutes for e in entries)
    tasks = db.list_tasks(db_path=db_path)
    completed = [t for t in tasks if t.status == STATUS_DONE]
    overdue = [t for t in tasks if t.is_overdue]
    return (
        f"This week: {total_minutes} minutes logged, "
        f"{len(completed)} task(s) completed, {len(overdue)} overdue."
    )


class NotificationScheduler:
    """Wraps an APScheduler BackgroundScheduler with the app's three jobs:
    - frequent deadline check (instant/upcoming-deadline alerts)
    - daily digest
    - weekly digest
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        in_app_fallback: Optional[InAppNotifier] = None,
        deadline_check_minutes: int = 30,
    ):
        self.db_path = db_path
        self.in_app_fallback = in_app_fallback
        self.deadline_check_minutes = deadline_check_minutes
        self.scheduler = BackgroundScheduler()
        self._notified_deadline_task_ids: set = set()

    def _check_deadlines(self) -> None:
        try:
            upcoming = upcoming_deadline_tasks(self.db_path, within_hours=24)
            for task in upcoming:
                if task.id in self._notified_deadline_task_ids:
                    continue
                send_notification(
                    "Deadline approaching",
                    f"'{task.title}' is due {task.deadline}",
                    self.in_app_fallback,
                )
                self._notified_deadline_task_ids.add(task.id)
        except Exception as exc:  # noqa: BLE001 - scheduler jobs must never crash
            logger.warning("Deadline check failed: %s", exc)

    def _send_daily_digest(self) -> None:
        try:
            send_notification("Daily digest", build_daily_digest_text(self.db_path), self.in_app_fallback)
        except Exception as exc:
            logger.warning("Daily digest failed: %s", exc)

    def _send_weekly_digest(self) -> None:
        try:
            send_notification("Weekly summary", build_weekly_digest_text(self.db_path), self.in_app_fallback)
        except Exception as exc:
            logger.warning("Weekly digest failed: %s", exc)

    def start(
        self,
        daily_digest_hour: int = 9,
        weekly_digest_day_of_week: str = "mon",
        weekly_digest_hour: int = 9,
    ) -> None:
        self.scheduler.add_job(
            self._check_deadlines,
            IntervalTrigger(minutes=self.deadline_check_minutes),
            id="deadline_check",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._send_daily_digest,
            CronTrigger(hour=daily_digest_hour, minute=0),
            id="daily_digest",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._send_weekly_digest,
            CronTrigger(day_of_week=weekly_digest_day_of_week, hour=weekly_digest_hour, minute=0),
            id="weekly_digest",
            replace_existing=True,
        )
        self.scheduler.start()

    def shutdown(self) -> None:
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:
            pass
