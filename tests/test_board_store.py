from __future__ import annotations

from pathlib import Path

from app.services.board_store import BoardStore, default_note, default_task, default_todo_item


def make_store(tmp_path: Path) -> BoardStore:
    return BoardStore(str(tmp_path / "data"))


def test_board_store_creates_default_board(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    board = store.load()

    assert board["board_title"]
    assert board["statuses"]
    assert isinstance(board["tasks"], list)
    assert (tmp_path / "data" / "workspaces" / "personal" / "board.json").exists()


def test_board_store_saves_and_loads_board(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    board = store.load()
    board["board_title"] = "Saved board"
    board["tasks"] = []
    store.save(board)

    loaded = store.load()

    assert loaded["board_title"] == "Saved board"
    assert loaded["tasks"] == []


def test_board_store_normalises_missing_fields_and_legacy_mermaid(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    raw_board = {
        "statuses": ["Backlog"],
        "tasks": [{"id": "task1", "title": "Legacy", "mermaid_code": "flowchart TD\nA-->B"}],
    }
    store.save(raw_board)

    loaded = store.load()
    task = loaded["tasks"][0]

    assert "summary" in task
    assert "repo_context" in task
    assert task["mermaid_artifacts"]["flow"] == "flowchart TD\nA-->B"


def test_board_store_adds_updates_and_deletes_task(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    task = default_task()
    task["title"] = "Created task"
    store.add_task(task)

    created = next(item for item in store.load()["tasks"] if item["id"] == task["id"])
    assert created["title"] == "Created task"

    store.update_task(task["id"], {"summary": "Updated summary"})
    updated = next(item for item in store.load()["tasks"] if item["id"] == task["id"])
    assert updated["summary"] == "Updated summary"

    store.delete_task(task["id"])
    assert all(item["id"] != task["id"] for item in store.load()["tasks"])


def test_board_store_adds_notes_and_todos(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    note = default_note()
    note["title"] = "Note"
    todo = default_todo_item()
    todo["text"] = "Todo"

    store.add_note(note)
    store.add_todo_item(todo)

    board = store.load()
    assert board["notes"][0]["title"] == "Note"
    assert board["todo_items"][0]["text"] == "Todo"


def test_board_store_appends_agent_and_executor_runs(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    task = default_task()
    task["title"] = "Run task"
    store.add_task(task)

    executor_run = {"id": "run1", "kind": "executor:generate_mermaid", "summary": "Done"}
    agent_run = {"id": "run2", "kind": "task-agent", "summary": "Agent"}
    store.append_task_run(task["id"], executor_run)
    store.append_agent_run(agent_run)

    board = store.load()
    saved_task = next(item for item in board["tasks"] if item["id"] == task["id"])
    assert saved_task["executor_runs"][0]["id"] == "run1"
    assert board["agent_runs"][0]["id"] == "run2"
