from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_STATUSES = ["Backlog", "Ready", "In Progress", "Blocked", "Review", "Done"]
DEFAULT_EXECUTOR_ACTIONS = [
    "repo_scan",
    "diff_summary",
    "generate_mermaid",
    "document_parse",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid4().hex[:10]


def default_mermaid_artifacts() -> dict[str, str]:
    return {
        "architecture": "",
        "flow": "",
        "kanban_subview": "",
        "sequence": "",
        "mindmap": "",
    }


def default_repo_context() -> dict[str, Any]:
    return {
        "repo_path": "",
        "focus_patterns": "*.py,*.md,*.json",
        "notes": "",
        "repo_root": "",
        "is_git_repo": False,
        "sample_files": [],
        "selected_files": [],
        "git_status": [],
        "recent_commits": [],
        "documents": [],
        "summary": "",
        "last_ingested_at": "",
    }


def default_task() -> dict[str, Any]:
    return {
        "id": new_id(),
        "title": "Untitled task",
        "summary": "",
        "status": "Backlog",
        "priority": "Medium",
        "labels": [],
        "owner": "PUXAI",
        "checklist": [],
        "agent_brief": "",
        "latest_agent_notes": "",
        "notes": "",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "mermaid_artifacts": default_mermaid_artifacts(),
        "repo_context": default_repo_context(),
        "executor_runs": [],
        "last_executor_action": "",
        "last_executor_notes": "",
        "executor_actions": list(DEFAULT_EXECUTOR_ACTIONS),
        "attachments": [],
        "email_drafts": [],
    }


def default_board() -> dict[str, Any]:
    cross_platform = default_task()
    cross_platform.update(
        {
            "title": "Finish the cross-platform PUXAI shell",
            "summary": "Polish the Flask shell, launcher hooks, and local workflow ergonomics.",
            "status": "In Progress",
            "priority": "High",
            "labels": ["platform", "ux"],
            "checklist": [
                {"text": "Confirm Windows, macOS, and Linux launchers", "done": False},
                {"text": "Keep the local-first interaction model clean", "done": False},
            ],
            "agent_brief": "Make the product feel like an AI operating console rather than a plain CRUD app.",
        }
    )
    mermaid_task = default_task()
    mermaid_task.update(
        {
            "title": "Add Mermaid kanban support directly into the board",
            "summary": "Each task can carry Mermaid context and the whole board exports to Mermaid kanban syntax.",
            "status": "Ready",
            "priority": "Medium",
            "labels": ["mermaid", "planning"],
            "checklist": [
                {"text": "Board-level Mermaid export", "done": False},
                {"text": "Task-level Mermaid snippets", "done": False},
            ],
            "agent_brief": "Use Mermaid as a first-class planning artifact.",
        }
    )
    return {
        "board_title": "PUXAI Agentic Workspace",
        "board_summary": (
            "An AI-enabled control room for work planning, local launches, and "
            "Mermaid-powered task visualization."
        ),
        "statuses": list(DEFAULT_STATUSES),
        "tasks": [cross_platform, mermaid_task],
        "agent_runs": [],
        "chat_history": [],
        "board_mermaid_artifacts": {
            "kanban": "",
            "stitched": "",
        },
        "ideas": [
            "Let agents generate next actions instead of static task descriptions.",
            "Blend Mermaid diagrams with kanban cards so system design stays attached to delivery work.",
        ],
        "updated_at": utc_now(),
    }


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

    def append_task_run(self, task_id: str, run: dict[str, Any]) -> dict[str, Any]:
        board = self.load()
        for task in board["tasks"]:
            if task["id"] == task_id:
                task.setdefault("executor_runs", []).insert(0, run)
                task["executor_runs"] = task["executor_runs"][:12]
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
            task = _normalize_task(raw_task, board["statuses"])
            normalized_tasks.append(task)
        board["tasks"] = normalized_tasks
        board["agent_runs"] = list(board.get("agent_runs", []))
        board["chat_history"] = list(board.get("chat_history", []))
        board["ideas"] = list(board.get("ideas", []))
        board["board_mermaid_artifacts"] = {
            "kanban": str(
                (board.get("board_mermaid_artifacts", {}) or {}).get(
                    "kanban",
                    board.get("board_mermaid", ""),
                )
            ),
            "stitched": str((board.get("board_mermaid_artifacts", {}) or {}).get("stitched", "")),
        }
        board.pop("board_mermaid", None)
        return board


def _normalize_task(raw_task: dict[str, Any], valid_statuses: list[str]) -> dict[str, Any]:
    base = default_task()
    task = {
        "id": raw_task.get("id") or base["id"],
        "title": raw_task.get("title", base["title"]).strip() or base["title"],
        "summary": raw_task.get("summary", "").strip(),
        "status": raw_task.get("status", "Backlog"),
        "priority": raw_task.get("priority", "Medium"),
        "labels": list(raw_task.get("labels", [])),
        "owner": raw_task.get("owner", "PUXAI"),
        "checklist": list(raw_task.get("checklist", [])),
        "agent_brief": raw_task.get("agent_brief", "").strip(),
        "latest_agent_notes": raw_task.get("latest_agent_notes", "").strip(),
        "notes": raw_task.get("notes", "").strip(),
        "created_at": raw_task.get("created_at", utc_now()),
        "updated_at": raw_task.get("updated_at", utc_now()),
        "executor_runs": list(raw_task.get("executor_runs", [])),
        "last_executor_action": str(raw_task.get("last_executor_action", "")),
        "last_executor_notes": str(raw_task.get("last_executor_notes", "")),
        "executor_actions": list(raw_task.get("executor_actions", DEFAULT_EXECUTOR_ACTIONS)),
        "attachments": list(raw_task.get("attachments", [])),
        "email_drafts": list(raw_task.get("email_drafts", [])),
    }
    if task["status"] not in valid_statuses:
        task["status"] = valid_statuses[0]

    artifacts = default_mermaid_artifacts()
    artifacts.update(raw_task.get("mermaid_artifacts", {}) or {})
    legacy_mermaid = str(raw_task.get("mermaid_code", "")).strip()
    if legacy_mermaid and not artifacts["flow"]:
        artifacts["flow"] = legacy_mermaid
    task["mermaid_artifacts"] = {key: str(value).strip() for key, value in artifacts.items()}

    repo_context = default_repo_context()
    repo_context.update(raw_task.get("repo_context", {}) or {})
    task["repo_context"] = {
        "repo_path": str(repo_context.get("repo_path", "")).strip(),
        "focus_patterns": str(repo_context.get("focus_patterns", "*.py,*.md,*.json")).strip(),
        "notes": str(repo_context.get("notes", "")).strip(),
        "repo_root": str(repo_context.get("repo_root", "")).strip(),
        "is_git_repo": bool(repo_context.get("is_git_repo", False)),
        "sample_files": list(repo_context.get("sample_files", [])),
        "selected_files": list(repo_context.get("selected_files", [])),
        "git_status": list(repo_context.get("git_status", [])),
        "recent_commits": list(repo_context.get("recent_commits", [])),
        "documents": list(repo_context.get("documents", [])),
        "summary": str(repo_context.get("summary", "")).strip(),
        "last_ingested_at": str(repo_context.get("last_ingested_at", "")).strip(),
    }
    return task
