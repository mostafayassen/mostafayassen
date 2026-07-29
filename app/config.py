"""Small JSON-backed settings store shared by settings_view.py and the rest
of the app (which sync folder to use, which Ollama model, the user's Azure
AD client id, notification preferences).

Kept deliberately tiny -- this is not meant to be a general config
framework, just enough persistence for the handful of settings the app
exposes in Settings view.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

from app.db import default_db_path
from app.integrations.ai_provider import DEFAULT_MODEL, DEFAULT_OLLAMA_HOST

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".task_organizer")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


@dataclass
class AppConfig:
    db_path: str = field(default_factory=default_db_path)
    sync_folder: str = ""  # empty = not using a OneDrive sync folder
    ollama_host: str = DEFAULT_OLLAMA_HOST
    ollama_model: str = DEFAULT_MODEL
    azure_client_id: str = ""  # see README "Outlook & Teams setup"
    notify_daily_digest: bool = True
    notify_weekly_digest: bool = True
    notify_deadline_alerts: bool = True
    deadline_alert_hours: int = 24


def load_config(path: str = CONFIG_PATH) -> AppConfig:
    if not os.path.exists(path):
        return AppConfig()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        defaults = asdict(AppConfig())
        defaults.update({k: v for k, v in data.items() if k in defaults})
        return AppConfig(**defaults)
    except (OSError, json.JSONDecodeError, TypeError):
        return AppConfig()


def save_config(config: AppConfig, path: str = CONFIG_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2)
