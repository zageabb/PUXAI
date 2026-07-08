from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4


DEFAULT_STATUSES = ["Backlog", "Ready", "In Progress", "Blocked", "Review", "Done"]
DEFAULT_WORKSPACE_ID = "personal"
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


def default_note() -> dict[str, Any]:
    return {
        "id": new_id(),
        "title": "Untitled note",
        "body": "",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


def default_todo_item() -> dict[str, Any]:
    return {
        "id": new_id(),
        "text": "",
        "done": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


def default_activity_event() -> dict[str, Any]:
    return {
        "id": new_id(),
        "scope": "board",
        "task_id": "",
        "kind": "",
        "title": "",
        "summary": "",
        "payload": {},
        "created_at": utc_now(),
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
        "notes": [],
        "todo_items": [],
        "agent_runs": [],
        "activity": [],
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


def default_workspace_metadata(
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    name: str = "Personal",
    description: str = "Default local PUXAI workspace.",
) -> dict[str, str]:
    now = utc_now()
    return {
        "id": workspace_id,
        "name": name,
        "description": description,
        "created_at": now,
        "updated_at": now,
    }


class BoardStore:
    def __init__(self, data_dir: str, default_workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.legacy_board_file = self.data_dir / "board.json"
        self.workspaces_dir = self.data_dir / "workspaces"
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "workspace_state.json"
        normalized_default = self._slugify_workspace_id(default_workspace_id) or DEFAULT_WORKSPACE_ID
        self.default_workspace_id = normalized_default
        self._ensure_workspace_structure()

    def load(self, workspace_id: str | None = None) -> dict[str, Any]:
        board_file = self._workspace_board_file(workspace_id)
        if not board_file.exists():
            board = default_board()
            metadata = self.get_workspace(workspace_id) or default_workspace_metadata(
                self._active_workspace_id(workspace_id),
                self._humanize_workspace_name(self._active_workspace_id(workspace_id)),
                "Local PUXAI workspace.",
            )
            board["board_title"] = metadata["name"]
            if metadata["description"]:
                board["board_summary"] = metadata["description"]
            self.save(board, workspace_id=workspace_id)
            return self._normalize(board)
        try:
            payload = json.loads(board_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = default_board()
            self.save(payload, workspace_id=workspace_id)
        return self._normalize(payload)

    def save(self, payload: dict[str, Any], workspace_id: str | None = None) -> dict[str, Any]:
        active_workspace_id = self._active_workspace_id(workspace_id)
        normalized = self._normalize(payload)
        normalized["updated_at"] = utc_now()
        board_file = self._workspace_board_file(active_workspace_id)
        board_file.parent.mkdir(parents=True, exist_ok=True)
        board_file.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        metadata = self.get_workspace(active_workspace_id) or default_workspace_metadata(
            active_workspace_id,
            normalized.get("board_title", self._humanize_workspace_name(active_workspace_id)),
            normalized.get("board_summary", ""),
        )
        metadata["updated_at"] = normalized["updated_at"]
        self._save_workspace_metadata(metadata)
        return normalized

    def add_task(self, task: dict[str, Any]) -> dict[str, Any]:
        board = self.load()
        board["tasks"].append(task)
        return self.save(board)

    def add_note(self, note: dict[str, Any]) -> dict[str, Any]:
        board = self.load()
        board.setdefault("notes", []).insert(0, note)
        board["notes"] = board["notes"][:50]
        return self.save(board)

    def add_todo_item(self, todo_item: dict[str, Any]) -> dict[str, Any]:
        board = self.load()
        board.setdefault("todo_items", []).insert(0, todo_item)
        board["todo_items"] = board["todo_items"][:100]
        return self.save(board)

    def update_task(self, task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        board = self.load()
        for task in board["tasks"]:
            if task["id"] == task_id:
                task.update(patch)
                task["updated_at"] = utc_now()
                break
        return self.save(board)

    def delete_task(self, task_id: str) -> dict[str, Any]:
        board = self.load()
        board["tasks"] = [task for task in board["tasks"] if task["id"] != task_id]
        return self.save(board)

    def toggle_todo_item(self, todo_id: str) -> dict[str, Any]:
        board = self.load()
        for todo_item in board.get("todo_items", []):
            if todo_item["id"] == todo_id:
                todo_item["done"] = not todo_item.get("done", False)
                todo_item["updated_at"] = utc_now()
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

    def append_activity_event(self, event: dict[str, Any]) -> dict[str, Any]:
        board = self.load()
        normalized_event = _normalize_activity_event(event)
        board.setdefault("activity", []).insert(0, normalized_event)
        board["activity"] = board["activity"][:200]
        return self.save(board)

    def list_recent_activity(self, limit: int = 200) -> list[dict[str, Any]]:
        board = self.load()
        return list(board.get("activity", []))[: max(0, limit)]

    def list_task_activity(self, task_id: str, limit: int = 50) -> list[dict[str, Any]]:
        board = self.load()
        task_events = [
            event for event in board.get("activity", [])
            if str(event.get("task_id", "")).strip() == task_id
        ]
        return task_events[: max(0, limit)]

    def list_workspaces(self) -> list[dict[str, str]]:
        workspaces: list[dict[str, str]] = []
        for workspace_dir in sorted(self.workspaces_dir.iterdir(), key=lambda item: item.name):
            if not workspace_dir.is_dir():
                continue
            metadata = self.get_workspace(workspace_dir.name)
            if metadata is not None:
                workspaces.append(metadata)
        if not any(item["id"] == self.default_workspace_id for item in workspaces):
            workspaces.insert(
                0,
                default_workspace_metadata(
                    self.default_workspace_id,
                    self._humanize_workspace_name(self.default_workspace_id),
                    "Default local PUXAI workspace.",
                ),
            )
        return sorted(workspaces, key=lambda item: item["created_at"])

    def get_workspace(self, workspace_id: str | None = None) -> dict[str, str] | None:
        active_workspace_id = self._active_workspace_id(workspace_id)
        metadata_file = self._workspace_meta_file(active_workspace_id)
        if not metadata_file.exists():
            return None
        try:
            payload = json.loads(metadata_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return self._normalize_workspace_metadata(payload, active_workspace_id)

    def get_active_workspace_id(self) -> str:
        state = self._load_state()
        return self._validate_workspace_id(state.get("active_workspace_id", self.default_workspace_id))

    def get_active_workspace(self) -> dict[str, str]:
        workspace = self.get_workspace(self.get_active_workspace_id())
        if workspace is not None:
            return workspace
        fallback = default_workspace_metadata(
            self.default_workspace_id,
            self._humanize_workspace_name(self.default_workspace_id),
            "Default local PUXAI workspace.",
        )
        self._save_workspace_metadata(fallback)
        return fallback

    def set_active_workspace(self, workspace_id: str) -> dict[str, str]:
        metadata = self.get_workspace(workspace_id)
        if metadata is None:
            raise ValueError(f"Unknown workspace id: {workspace_id}")
        state = self._load_state()
        state["active_workspace_id"] = metadata["id"]
        self._save_state(state)
        return metadata

    def create_workspace(
        self,
        name: str,
        description: str = "",
        workspace_id: str | None = None,
    ) -> dict[str, str]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Workspace name is required.")
        preferred_id = self._slugify_workspace_id(workspace_id or clean_name) or DEFAULT_WORKSPACE_ID
        resolved_id = self._unique_workspace_id(preferred_id)
        metadata = default_workspace_metadata(resolved_id, clean_name, description.strip())
        self._save_workspace_metadata(metadata)
        board = default_board()
        board["board_title"] = clean_name
        if description.strip():
            board["board_summary"] = description.strip()
        self.save(board, workspace_id=resolved_id)
        self.set_active_workspace(resolved_id)
        return metadata

    def current_workspace_root(self) -> Path:
        return self._workspace_dir(self.get_active_workspace_id())

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
        board["notes"] = [_normalize_note(raw_note) for raw_note in board.get("notes", [])]
        board["todo_items"] = [
            _normalize_todo_item(raw_todo_item)
            for raw_todo_item in board.get("todo_items", [])
        ]
        board["agent_runs"] = list(board.get("agent_runs", []))
        board["activity"] = [
            _normalize_activity_event(raw_event)
            for raw_event in board.get("activity", [])
        ][:200]
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

    def _ensure_workspace_structure(self) -> None:
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        default_metadata = self.get_workspace(self.default_workspace_id)
        if default_metadata is None:
            self._save_workspace_metadata(
                default_workspace_metadata(
                    self.default_workspace_id,
                    self._humanize_workspace_name(self.default_workspace_id),
                    "Default local PUXAI workspace.",
                )
            )
        self._migrate_legacy_board()
        state = self._load_state()
        active_workspace_id = self._validate_workspace_id(
            state.get("active_workspace_id", self.default_workspace_id)
        )
        if self.get_workspace(active_workspace_id) is None:
            active_workspace_id = self.default_workspace_id
        self._save_state({"active_workspace_id": active_workspace_id})

    def _migrate_legacy_board(self) -> None:
        default_board_file = self._workspace_board_file(self.default_workspace_id)
        if default_board_file.exists():
            return
        if self.legacy_board_file.exists():
            try:
                payload = json.loads(self.legacy_board_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = default_board()
            normalized = self._normalize(payload)
            default_board_file.parent.mkdir(parents=True, exist_ok=True)
            default_board_file.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
            metadata = self.get_workspace(self.default_workspace_id) or default_workspace_metadata(
                self.default_workspace_id,
                normalized.get("board_title", self._humanize_workspace_name(self.default_workspace_id)),
                normalized.get("board_summary", "Migrated from the legacy single-board storage."),
            )
            metadata["updated_at"] = normalized.get("updated_at", utc_now())
            self._save_workspace_metadata(metadata)
            return
        self.save(default_board(), workspace_id=self.default_workspace_id)

    def _workspace_dir(self, workspace_id: str | None = None) -> Path:
        return self.workspaces_dir / self._active_workspace_id(workspace_id)

    def _workspace_board_file(self, workspace_id: str | None = None) -> Path:
        return self._workspace_dir(workspace_id) / "board.json"

    def _workspace_meta_file(self, workspace_id: str | None = None) -> Path:
        return self._workspace_dir(workspace_id) / "workspace.json"

    def _active_workspace_id(self, workspace_id: str | None = None) -> str:
        return self._validate_workspace_id(workspace_id or self.get_active_workspace_id())

    def _load_state(self) -> dict[str, str]:
        if not self.state_file.exists():
            return {"active_workspace_id": self.default_workspace_id}
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"active_workspace_id": self.default_workspace_id}
        return {
            "active_workspace_id": self._validate_workspace_id(
                payload.get("active_workspace_id", self.default_workspace_id)
            )
        }

    def _save_state(self, payload: dict[str, str]) -> None:
        self.state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _save_workspace_metadata(self, payload: dict[str, str]) -> dict[str, str]:
        metadata = self._normalize_workspace_metadata(payload, payload.get("id", self.default_workspace_id))
        metadata_file = self._workspace_meta_file(metadata["id"])
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return metadata

    def _normalize_workspace_metadata(self, payload: dict[str, Any], fallback_id: str) -> dict[str, str]:
        now = utc_now()
        workspace_id = self._validate_workspace_id(payload.get("id", fallback_id))
        return {
            "id": workspace_id,
            "name": str(payload.get("name", self._humanize_workspace_name(workspace_id))).strip()
            or self._humanize_workspace_name(workspace_id),
            "description": str(payload.get("description", "")).strip(),
            "created_at": str(payload.get("created_at", now)),
            "updated_at": str(payload.get("updated_at", now)),
        }

    def _unique_workspace_id(self, base_id: str) -> str:
        if self.get_workspace(base_id) is None:
            return base_id
        suffix = 2
        while self.get_workspace(f"{base_id}-{suffix}") is not None:
            suffix += 1
        return f"{base_id}-{suffix}"

    def _validate_workspace_id(self, workspace_id: str | None) -> str:
        normalized = self._slugify_workspace_id(workspace_id or "")
        return normalized or self.default_workspace_id

    def _slugify_workspace_id(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower())
        return slug.strip("-")

    def _humanize_workspace_name(self, workspace_id: str) -> str:
        return workspace_id.replace("-", " ").title()


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


def _normalize_note(raw_note: dict[str, Any]) -> dict[str, Any]:
    base = default_note()
    return {
        "id": raw_note.get("id") or base["id"],
        "title": str(raw_note.get("title", base["title"])).strip() or base["title"],
        "body": str(raw_note.get("body", "")).strip(),
        "created_at": raw_note.get("created_at", base["created_at"]),
        "updated_at": raw_note.get("updated_at", base["updated_at"]),
    }


def _normalize_todo_item(raw_todo_item: dict[str, Any]) -> dict[str, Any]:
    base = default_todo_item()
    return {
        "id": raw_todo_item.get("id") or base["id"],
        "text": str(raw_todo_item.get("text", "")).strip(),
        "done": bool(raw_todo_item.get("done", False)),
        "created_at": raw_todo_item.get("created_at", base["created_at"]),
        "updated_at": raw_todo_item.get("updated_at", base["updated_at"]),
    }


def _normalize_activity_event(raw_event: dict[str, Any]) -> dict[str, Any]:
    base = default_activity_event()
    return {
        "id": str(raw_event.get("id", base["id"])).strip() or base["id"],
        "scope": str(raw_event.get("scope", "board")).strip() or "board",
        "task_id": str(raw_event.get("task_id", "")).strip(),
        "kind": str(raw_event.get("kind", "")).strip(),
        "title": str(raw_event.get("title", "")).strip(),
        "summary": str(raw_event.get("summary", "")).strip(),
        "payload": raw_event.get("payload", {}) if isinstance(raw_event.get("payload", {}), dict) else {},
        "created_at": str(raw_event.get("created_at", base["created_at"])).strip() or base["created_at"],
    }
