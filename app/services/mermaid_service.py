from __future__ import annotations

import re
from typing import Any


def build_kanban_mermaid(board: dict[str, Any]) -> str:
    lines = ["kanban"]
    tasks_by_status: dict[str, list[dict[str, Any]]] = {status: [] for status in board.get("statuses", [])}
    for task in board.get("tasks", []):
        tasks_by_status.setdefault(task["status"], []).append(task)

    for status in board.get("statuses", []):
        lines.append(f"    {status}")
        for task in tasks_by_status.get(status, []):
            task_id = safe_id(task["id"])
            title = clean_text(task["title"])
            metadata = []
            if task.get("owner"):
                metadata.append(f"assigned: '{clean_text(task['owner'])}'")
            if task.get("priority"):
                metadata.append(f"priority: '{clean_text(task['priority'])}'")
            metadata_suffix = f"@{{ {', '.join(metadata)} }}" if metadata else ""
            lines.append(f"        {task_id}[{title}]{metadata_suffix}")
    return "\n".join(lines)


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    return cleaned or "task"


def clean_text(value: str) -> str:
    return str(value).replace("[", "(").replace("]", ")").replace("\n", " ").strip()
