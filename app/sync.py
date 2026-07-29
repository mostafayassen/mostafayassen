"""Helpers for the "free mobile sync via OneDrive" story.

The app doesn't implement any cloud backend of its own (budget is $0). The
trick that gets tasks onto a phone anyway: point the SQLite database file at
a folder that OneDrive already syncs for you, and use the official OneDrive
mobile app to browse/open an *exported* view of your tasks (see
integrations/excel_io.py export functions) since SQLite files aren't
directly readable in a mobile Office/Files app the way an .xlsx is.

Practical recommended workflow (documented in more detail in README.md):
  1. In Settings, set the data folder to somewhere under your OneDrive
     folder, e.g. C:\\Users\\you\\OneDrive\\TaskOrganizer\\
  2. The app's .db file now syncs automatically to OneDrive's cloud storage
     alongside your other files.
  3. For actually *viewing/editing* tasks from your phone, use "Export to
     Excel" (see excel_io.export_tasks_to_xlsx) to write an .xlsx into that
     same OneDrive folder periodically (or before you leave your desk) --
     then open it with the OneDrive or Excel mobile app.
  4. This is NOT real-time two-way sync and there's no conflict resolution
     beyond whatever OneDrive itself provides for the raw .db file (last
     writer wins if you somehow ran the desktop app on two machines at the
     same time, which you shouldn't for a single SQLite file). Don't run
     the app on two machines against the same synced .db file
     simultaneously.

This module intentionally does not talk to any OneDrive/Microsoft API --
"sync" here just means "put the file in a folder OneDrive already
watches", which requires no auth, no cost, and no extra dependency.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from typing import Optional


class SyncPathError(Exception):
    """Raised when a configured sync folder path is invalid/unwritable."""


def looks_like_onedrive_path(path: str) -> bool:
    """Best-effort heuristic to warn users who picked a non-OneDrive folder.
    Not authoritative -- OneDrive folder names/locations are configurable,
    this is just a friendly nudge in the Settings UI."""
    lowered = path.lower()
    return "onedrive" in lowered


def ensure_sync_folder(path: str) -> str:
    """Create the folder if needed and confirm it's writable. Returns the
    absolute path. Raises SyncPathError on failure."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    try:
        os.makedirs(abs_path, exist_ok=True)
        probe = os.path.join(abs_path, ".task_organizer_write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
    except OSError as exc:
        raise SyncPathError(f"Can't write to '{abs_path}': {exc}") from exc
    return abs_path


def db_path_in_sync_folder(sync_folder: str, filename: str = "task_organizer.db") -> str:
    return os.path.join(ensure_sync_folder(sync_folder), filename)


def migrate_db_file(old_path: str, new_folder: str) -> str:
    """Move an existing database file into a (new) sync folder. Returns the
    new full path. Used by Settings when the user changes their sync
    folder after already having data."""
    new_path = db_path_in_sync_folder(new_folder, filename=os.path.basename(old_path))
    if os.path.abspath(old_path) == os.path.abspath(new_path):
        return new_path
    if os.path.exists(old_path):
        shutil.copy2(old_path, new_path)
    return new_path


def export_snapshot_filename(prefix: str = "tasks_export") -> str:
    """A timestamped filename suitable for periodic Excel exports into the
    sync folder, e.g. tasks_export_2026-07-29_0800.xlsx"""
    return f"{prefix}_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
