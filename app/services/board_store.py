from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_STATUSES = ["Backlog", "Ready", "In Progress", "Blocked", "Review", "Done"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_board() -> dict[str, Any]:
    return {
        "board_title": "PUXAI Agentic Workspace",
        "board_summary": (
            "An AI-enabled control room for work planning, local launches, and "
            "Mermaid-powered task visualization."
        ),
        "statuses": list(DEFAULT_STATUSES),
        "tasks": [
            {
                "id": new_id(),
                "title": "Finish the cross-platform PUXAI shell",
                "summary": "Polish the Flask shell, launcher hooks, and local workflow ergonomics.",
                "status": "In Progress",
                "priority": "High",
                "labels": ["platform", "ux"],
                "owner": "PUXAI",
                "checklist": [
                    {"text": "Confirm Windows, macOS, and Linux launchers", "done": False},
                    {"text": "Keep the local-first interaction model clean", "done": False},
                ],
                "agent_brief": "Make the product feel like an AI operating console rather than a plain CRUD app.",
                "mermaid_code": "",
                "latest_agent_notes": "",
                "created_at": utc_now(),
                "updated_at": utc_now(),
            },
            {
                "id": new_id(),
                "title": "Add Mermaid kanban support directly into the board",
                "summary": "Each task can carry Mermaid context and the whole board exports to Mermaid kanban syntax.",
                "status": "Ready",
                "priority": "Medium",
                "labels": ["mermaid", "planning"],
                "owner": "PUXAI",
                "checklist": [
                    {"text": "Board-level Mermaid export", "done": False},
                    {"text": "Task-level Mermaid snippets", "done": False},
                ],
                "agent_brief": "Use Mermaid as a first-class planning artifact.",
                "mermaid_code": "",
                "latest_agent_notes": "",
                "created_at": utc_now(),
                "updated_at": utc_now(),
            },
        ],
        "agent_runs": [],
        "chat_history": [],
        "board_mermaid": "",
        "ideas": [
            "Let agents generate next actions instead of static task descriptions.",
            "Blend Mermaid diagrams with kanban cards so system design stays attached to delivery work.",
        ],
        "updated_at": utc_now(),
    }


def new_id() -> str:
    return uuid4().hex[:10]


class BoardStore:
    def __init__(self, data_dir: str) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.board_file = self.data_dir / "board.json"

    def load(self) -> dict[str, Any]:
        if not self.board_file.exists():
            board = default_board()
            self.save(board)
            return board
        try:
            payload = json.loads(self.board_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = default_board()
            self.save(payload)
        return self._normalize(payload)

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize(payload)
        normalized["updated_at"] = utc_now()
        self.board_file.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        return normalized

    def add_task(self, task: dict[str, Any]) -> dict[str, Any]:
        board = self.load()
        board["tasks"].append(task)
        return self.save(board)

    def update_task(self, task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        board = self.load()
        for task in board["tasks"]:
            if task["id"] == task_id:
                task.update(patch)
                task["updated_at"] = utc_now()
                break
        return self.save(board)

    def append_agent_run(self, run: dict[str, Any]) -> dict[str, Any]:
        board = self.load()
        board["agent_runs"].insert(0, run)
        return self.save(board)

    def append_chat_message(self, message: dict[str, Any]) -> dict[str, Any]:
        board = self.load()
        board["chat_history"].append(message)
        board["chat_history"] = board["chat_history"][-20:]
        return self.save(board)

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        board = deepcopy(default_board())
        board.update(payload or {})
        board["statuses"] = [status for status in board.get("statuses", DEFAULT_STATUSES) if status] or list(
            DEFAULT_STATUSES
        )
        normalized_tasks = []
        for raw_task in board.get("tasks", []):
            task = {
                "id": raw_task.get("id") or new_id(),
                "title": raw_task.get("title", "Untitled task").strip() or "Untitled task",
                "summary": raw_task.get("summary", "").strip(),
                "status": raw_task.get("status", "Backlog"),
                "priority": raw_task.get("priority", "Medium"),
                "labels": list(raw_task.get("labels", [])),
                "owner": raw_task.get("owner", "PUXAI"),
                "checklist": list(raw_task.get("checklist", [])),
                "agent_brief": raw_task.get("agent_brief", "").strip(),
                "mermaid_code": raw_task.get("mermaid_code", "").strip(),
                "latest_agent_notes": raw_task.get("latest_agent_notes", "").strip(),
                "created_at": raw_task.get("created_at", utc_now()),
                "updated_at": raw_task.get("updated_at", utc_now()),
            }
            if task["status"] not in board["statuses"]:
                task["status"] = board["statuses"][0]
            normalized_tasks.append(task)
        board["tasks"] = normalized_tasks
        board["agent_runs"] = list(board.get("agent_runs", []))
        board["chat_history"] = list(board.get("chat_history", []))
        board["ideas"] = list(board.get("ideas", []))
        board["board_mermaid"] = str(board.get("board_mermaid", ""))
        return board
