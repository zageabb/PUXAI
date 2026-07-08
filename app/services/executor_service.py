from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from app.services.board_store import new_id, utc_now
from app.services.mermaid_service import build_task_mermaid_artifacts
from app.services.repo_context_service import ingest_repository_context, json_preview, read_document_summary


SAFE_ACTIONS = {"repo_scan", "diff_summary", "generate_mermaid", "document_parse"}
EXECUTOR_ACTION_METADATA = {
    "repo_scan": {
        "id": "repo_scan",
        "label": "Repository scan",
        "description": "Index files and refresh repository context from the linked path.",
        "risk_level": "low",
        "requires_confirmation": False,
    },
    "diff_summary": {
        "id": "diff_summary",
        "label": "Diff summary",
        "description": "Read local git diff and status information from the linked repository.",
        "risk_level": "low",
        "requires_confirmation": False,
    },
    "generate_mermaid": {
        "id": "generate_mermaid",
        "label": "Generate Mermaid",
        "description": "Refresh task Mermaid artifacts from the current task and repo context.",
        "risk_level": "low",
        "requires_confirmation": False,
    },
    "document_parse": {
        "id": "document_parse",
        "label": "Parse documents",
        "description": "Read selected task files and extract lightweight summaries into task context.",
        "risk_level": "medium",
        "requires_confirmation": True,
    },
}


def get_executor_action_metadata(action: str) -> dict[str, Any]:
    normalized_action = action.strip().lower()
    metadata = EXECUTOR_ACTION_METADATA.get(normalized_action)
    if metadata is None:
        raise ValueError(f"Unsupported executor action: {action}")
    return dict(metadata)


def list_executor_actions(actions: list[str]) -> list[dict[str, Any]]:
    return [get_executor_action_metadata(action) for action in actions if action.strip().lower() in SAFE_ACTIONS]


def preview_task_action(task: dict[str, Any], action: str) -> dict[str, Any]:
    normalized_action = action.strip().lower()
    metadata = get_executor_action_metadata(normalized_action)
    repo_context = task.get("repo_context", {}) or {}
    if normalized_action == "repo_scan":
        preview_lines = [
            f"Repository path: {repo_context.get('repo_path', '') or 'Not set'}",
            f"Focus patterns: {repo_context.get('focus_patterns', '*.py,*.md,*.json')}",
        ]
    elif normalized_action == "diff_summary":
        preview_lines = [
            f"Repository root: {repo_context.get('repo_root') or repo_context.get('repo_path') or 'Not set'}",
        ]
    elif normalized_action == "generate_mermaid":
        preview_lines = [
            "Task Mermaid artifacts will be refreshed.",
            "Current architecture, flow, kanban subview, sequence, and mindmap fields may be replaced.",
        ]
    else:
        selected_files = repo_context.get("selected_files", [])[:6]
        preview_lines = selected_files or ["No selected files are available yet."]

    return {
        **metadata,
        "preview_lines": preview_lines,
    }


def execute_task_action(task: dict[str, Any], action: str) -> dict[str, Any]:
    normalized_action = action.strip().lower()
    if normalized_action not in SAFE_ACTIONS:
        raise ValueError(f"Unsupported executor action: {action}")

    if normalized_action == "repo_scan":
        return _repo_scan(task)
    if normalized_action == "diff_summary":
        return _diff_summary(task)
    if normalized_action == "generate_mermaid":
        return _generate_mermaid(task)
    return _document_parse(task)


def record_executor_run(task_id: str, action: str, summary: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": new_id(),
        "task_id": task_id,
        "kind": f"executor:{action}",
        "summary": summary,
        "payload": payload,
        "created_at": utc_now(),
    }


def _repo_scan(task: dict[str, Any]) -> dict[str, Any]:
    repo_context = task.get("repo_context", {}) or {}
    path = repo_context.get("repo_path", "")
    if not path:
        raise ValueError("Set a repository path before running repo_scan.")
    refreshed = ingest_repository_context(path, repo_context.get("focus_patterns", "*.py,*.md,*.json"), repo_context.get("notes", ""))
    return {
        "summary": f"Repo scan indexed {len(refreshed['sample_files'])} sample files from {refreshed['repo_root']}.",
        "task_patch": {"repo_context": refreshed, "last_executor_action": "repo_scan", "last_executor_notes": refreshed["summary"]},
        "display": json_preview(refreshed),
    }


def _diff_summary(task: dict[str, Any]) -> dict[str, Any]:
    repo_context = task.get("repo_context", {}) or {}
    root = repo_context.get("repo_root") or repo_context.get("repo_path")
    if not root:
        raise ValueError("Set a repository path before running diff_summary.")
    try:
        diff_stat = subprocess.run(
            ["git", "-C", str(root), "diff", "--stat"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except Exception as exc:
        raise ValueError(f"Could not read git diff summary: {exc}") from exc
    summary = diff_stat or "No unstaged diff summary was returned."
    notes = status or "Working tree appears clean."
    return {
        "summary": "Collected a local git diff summary for the linked repository.",
        "task_patch": {"last_executor_action": "diff_summary", "last_executor_notes": f"{summary}\n{notes}".strip()},
        "display": f"{summary}\n\n{notes}".strip(),
    }


def _generate_mermaid(task: dict[str, Any]) -> dict[str, Any]:
    artifacts = build_task_mermaid_artifacts(task)
    return {
        "summary": "Generated architecture, flow, and kanban-subview Mermaid artifacts.",
        "task_patch": {
            "mermaid_artifacts": {**task.get("mermaid_artifacts", {}), **artifacts},
            "last_executor_action": "generate_mermaid",
            "last_executor_notes": "Mermaid artifacts regenerated from the current task and repo context.",
        },
        "display": json_preview(artifacts),
    }


def _document_parse(task: dict[str, Any]) -> dict[str, Any]:
    repo_context = task.get("repo_context", {}) or {}
    repo_root = repo_context.get("repo_root") or repo_context.get("repo_path")
    selected_files = repo_context.get("selected_files", [])[:6]
    if not repo_root or not selected_files:
        raise ValueError("Repo context needs at least one selected file before running document_parse.")
    documents = [read_document_summary(Path(repo_root) / relative_path) for relative_path in selected_files]
    updated_context = dict(repo_context)
    updated_context["documents"] = documents
    return {
        "summary": f"Parsed {len(documents)} selected files into lightweight task context.",
        "task_patch": {
            "repo_context": updated_context,
            "last_executor_action": "document_parse",
            "last_executor_notes": "Document summaries refreshed from selected files.",
        },
        "display": json_preview(documents),
    }
