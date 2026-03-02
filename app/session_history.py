"""Helpers for reading and writing session launch history."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

from app.launchers.base_launcher import LaunchableApp

LOGGER = logging.getLogger(__name__)


def get_history_file(data_dir: str) -> Path:
    """Return the session history JSON path."""

    return Path(data_dir) / "session_history.json"


def read_session_history(history_file: Path) -> list[dict[str, Any]]:
    """Load history entries from disk."""

    if not history_file.exists():
        return []

    with history_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        LOGGER.warning("Session history file is not a list: %s", history_file)
        return []

    return payload


def append_launch_event(history_file: Path, app: LaunchableApp) -> None:
    """Append a single launch event to session history."""

    history_file.parent.mkdir(parents=True, exist_ok=True)

    history = read_session_history(history_file)
    history.append(
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "app_id": app.id,
            "app_name": app.name,
            "category": app.category,
        }
    )

    with history_file.open("w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2)


def format_history_entry(entry: dict[str, Any]) -> str:
    """Return a user-friendly string for displaying history entries."""

    timestamp = entry.get("timestamp_utc", "unknown time")
    app_name = entry.get("app_name", "Unknown app")
    app_id = entry.get("app_id", "unknown-id")
    return f"{timestamp} — {app_name} ({app_id})"
