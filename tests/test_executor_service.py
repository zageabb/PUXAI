from __future__ import annotations

import pytest

from app.services.board_store import default_task
from app.services.executor_service import execute_task_action


def test_executor_rejects_unsupported_actions() -> None:
    with pytest.raises(ValueError, match="Unsupported executor action"):
        execute_task_action(default_task(), "unsupported")


def test_generate_mermaid_returns_task_patch() -> None:
    task = default_task()
    task["title"] = "Mermaid me"

    result = execute_task_action(task, "generate_mermaid")

    assert "task_patch" in result
    assert "mermaid_artifacts" in result["task_patch"]
    assert result["task_patch"]["last_executor_action"] == "generate_mermaid"


def test_document_parse_fails_without_selected_files() -> None:
    task = default_task()
    task["repo_context"]["repo_path"] = "/tmp/repo"
    task["repo_context"]["repo_root"] = "/tmp/repo"
    task["repo_context"]["selected_files"] = []

    with pytest.raises(ValueError, match="selected file"):
        execute_task_action(task, "document_parse")
