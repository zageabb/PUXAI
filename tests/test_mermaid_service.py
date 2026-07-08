from __future__ import annotations

from app.services.board_store import default_board, default_task
from app.services.mermaid_service import (
    build_kanban_mermaid,
    build_stitched_board_mermaid,
    build_task_mermaid_artifacts,
    clean_text,
)


def test_build_kanban_mermaid_generates_board_view() -> None:
    board = default_board()

    result = build_kanban_mermaid(board)

    assert result.startswith("kanban")
    assert "Backlog" in result or "In Progress" in result


def test_build_stitched_board_mermaid_generates_flowchart() -> None:
    board = default_board()

    result = build_stitched_board_mermaid(board)

    assert result.startswith("flowchart TD")
    assert 'board["PUXAI Board"]' in result


def test_build_task_mermaid_artifacts_generates_expected_keys() -> None:
    task = default_task()
    task["title"] = "Task title"
    task["repo_context"]["selected_files"] = ["app/main.py"]

    artifacts = build_task_mermaid_artifacts(task)

    assert set(artifacts) == {"architecture", "flow", "kanban_subview", "sequence", "mindmap"}
    assert artifacts["architecture"].startswith("flowchart LR")
    assert artifacts["flow"].startswith("flowchart TD")
    assert artifacts["sequence"].startswith("sequenceDiagram")


def test_clean_text_removes_unsafe_mermaid_label_characters() -> None:
    cleaned = clean_text('Task ["quoted"]\nline')

    assert "[" not in cleaned
    assert "]" not in cleaned
    assert '"' not in cleaned
    assert "\n" not in cleaned
