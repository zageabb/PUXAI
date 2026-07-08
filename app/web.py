"""Flask application for the PUXAI local workspace."""

from __future__ import annotations

from io import BytesIO
import logging
from pathlib import Path
import re
import shutil
from typing import Any

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, send_from_directory, url_for
from markupsafe import Markup, escape
from werkzeug.utils import secure_filename

from app.config import AppConfig, load_config, save_config
from app.launchers import BaseLauncher
from app.session_history import append_launch_event
from app.services.agent_service import (
    board_chat_action_plan,
    board_chat_reply,
    draft_task_with_ai,
    record_agent_run,
    run_task_agent,
)
from app.services.ai_backend import create_ai_backend
from app.services.board_store import (
    BoardStore,
    default_mermaid_artifacts,
    default_note,
    default_repo_context,
    default_todo_item,
    new_id,
    utc_now,
)
from app.services.executor_service import (
    execute_task_action,
    get_executor_action_metadata,
    preview_task_action,
    record_executor_run,
)
from app.services.mermaid_service import build_kanban_mermaid, build_stitched_board_mermaid
from app.services.repo_context_service import ingest_repository_context

LOGGER = logging.getLogger(__name__)

try:
    import markdown as markdown_lib
except ImportError:  # pragma: no cover - optional dependency
    markdown_lib = None


def create_app(
    config: AppConfig,
    os_name: str,
    launcher: BaseLauncher | None,
    history_file: Path,
) -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["SECRET_KEY"] = "puxai-local-secret"
    app.config["APP_CONFIG"] = config
    app.config["CONFIG_PATH"] = "config.ini"
    app.config["OS_NAME"] = os_name
    app.config["LAUNCHER"] = launcher
    app.config["HISTORY_FILE"] = history_file
    app.config["BOARD_STORE"] = BoardStore(
        config.data_dir,
        default_workspace_id=config.workspace_default_id,
    )

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        store = _board_store(app)
        board = store.load()
        ai_status = _ai_status(config)
        return {
            "app_config": config,
            "os_name": os_name,
            "launchable_apps": launcher.list_apps() if launcher else [],
            "ai_status": ai_status,
            "workspace_list": store.list_workspaces(),
            "active_workspace": store.get_active_workspace(),
            "board_kanban_mermaid": board.get("board_mermaid_artifacts", {}).get("kanban", ""),
            "board_stitched_mermaid": board.get("board_mermaid_artifacts", {}).get("stitched", ""),
            "render_markdown": _render_markdown,
        }

    @app.get("/")
    def index() -> str:
        store = _board_store(app)
        board = store.load()
        _refresh_mermaid(app)
        board = store.load()
        return render_template(
            "index.html",
            board=board,
            tasks_by_status=_tasks_by_status(board),
            recent_activity=store.list_recent_activity(25),
            os_name=os_name,
        )

    @app.get("/settings")
    def settings() -> str:
        settings_config = load_config(app.config["CONFIG_PATH"])
        return render_template(
            "settings.html",
            settings_config=settings_config,
            settings_ai_status=_ai_status(settings_config),
            ai_backend_options=["ollama", "dummy", "openai", "azure_openai", "copilot"],
            restart_required=True,
        )

    @app.post("/settings")
    def save_settings() -> Any:
        config_path = app.config["CONFIG_PATH"]
        current = load_config(config_path)
        try:
            updated = _build_settings_config_from_form(request, current)
        except ValueError as exc:
            flash(str(exc), "warning")
            preview_config = _settings_preview_config(request.form, current)
            return render_template(
                "settings.html",
                settings_config=preview_config,
                settings_ai_status=_ai_status(preview_config),
                ai_backend_options=["ollama", "dummy", "openai", "azure_openai", "copilot"],
                restart_required=True,
            )

        save_config(updated, config_path)
        flash("Settings saved to config.ini. Restart the app to apply all changes.", "success")
        return redirect(url_for("settings"))

    @app.post("/workspaces")
    def create_workspace() -> Any:
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("A workspace name is required.", "warning")
            return redirect(url_for("index"))
        try:
            workspace = _board_store(app).create_workspace(name, description)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Workspace creation failed")
            flash(f"Workspace creation failed: {exc}", "danger")
            return redirect(url_for("index"))
        flash(f"Created workspace '{workspace['name']}'.", "success")
        return redirect(url_for("index"))

    @app.post("/workspaces/switch")
    def switch_workspace() -> Any:
        workspace_id = request.form.get("workspace_id", "").strip()
        if not workspace_id:
            flash("Choose a workspace first.", "warning")
            return redirect(url_for("index"))
        try:
            workspace = _board_store(app).set_active_workspace(workspace_id)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Workspace switch failed")
            flash(f"Workspace switch failed: {exc}", "danger")
            return redirect(url_for("index"))
        flash(f"Switched to workspace '{workspace['name']}'.", "success")
        return redirect(url_for("index"))

    @app.get("/tasks/new")
    def new_task() -> str:
        board = _board_store(app).load()
        return render_template(
            "task_new.html",
            board=board,
            default_status=board["statuses"][0] if board["statuses"] else "Backlog",
        )

    @app.get("/tasks/<task_id>/edit")
    def edit_task(task_id: str) -> Any:
        board = _board_store(app).load()
        task = _find_task(board, task_id)
        if task is None:
            abort(404)
        return render_template(
            "task_edit.html",
            board=board,
            task=task,
            checklist_text=_checklist_to_text(task.get("checklist", [])),
            task_activity=_board_store(app).list_task_activity(task_id, 50),
            executor_action_details=_task_executor_action_details(task),
        )

    @app.post("/tasks")
    def create_task() -> Any:
        board = _board_store(app).load()
        title = request.form.get("title", "").strip()
        summary = request.form.get("summary", "").strip()
        status = request.form.get("status", board["statuses"][0]).strip()
        owner = request.form.get("owner", "PUXAI").strip() or "PUXAI"
        priority = request.form.get("priority", "Medium").strip() or "Medium"
        labels = [item.strip() for item in request.form.get("labels", "").split(",") if item.strip()]
        ai_enrich = request.form.get("ai_enrich") == "1"

        if not title:
            flash("A task title is required.", "warning")
            return redirect(url_for("new_task"))
        task = _build_task_payload(
            board=board,
            title=title,
            summary=summary,
            status=status,
            priority=priority,
            labels=labels,
            owner=owner,
            ai_enrich=ai_enrich,
            config=config,
        )
        _board_store(app).add_task(task)
        _append_activity_event(
            app,
            scope="task",
            task_id=task["id"],
            kind="task.created",
            title="Task created",
            summary=f"Created task '{task['title']}' in {task['status']}.",
            payload={"status": task["status"], "priority": task["priority"]},
        )
        _refresh_mermaid(app)
        flash(f"Added task '{title}'.", "success")
        return redirect(url_for("index"))

    @app.post("/notes")
    def create_note() -> Any:
        title = request.form.get("title", "").strip() or "Untitled note"
        body = request.form.get("body", "").strip()
        if not body:
            flash("A markdown note body is required.", "warning")
            return redirect(url_for("index"))

        note = default_note()
        note.update(
            {
                "title": title,
                "body": body,
                "updated_at": utc_now(),
            }
        )
        _board_store(app).add_note(note)
        _append_activity_event(
            app,
            scope="board",
            kind="note.created",
            title="Note created",
            summary=f"Saved note '{title}'.",
            payload={"note_id": note["id"]},
        )
        flash(f"Saved note '{title}'.", "success")
        return redirect(url_for("index"))

    @app.post("/todos")
    def create_todo_item() -> Any:
        text = request.form.get("text", "").strip()
        if not text:
            flash("A todo item needs some text.", "warning")
            return redirect(url_for("index"))

        todo_item = default_todo_item()
        todo_item.update(
            {
                "text": text,
                "updated_at": utc_now(),
            }
        )
        _board_store(app).add_todo_item(todo_item)
        _append_activity_event(
            app,
            scope="board",
            kind="todo.created",
            title="Todo created",
            summary=f"Added todo '{text}'.",
            payload={"todo_id": todo_item["id"]},
        )
        flash("Added todo item.", "success")
        return redirect(url_for("index"))

    @app.post("/todos/<todo_id>/toggle")
    def toggle_todo_item(todo_id: str) -> Any:
        _board_store(app).toggle_todo_item(todo_id)
        return redirect(url_for("index"))

    @app.post("/capture/<source_type>/<source_id>/task")
    def create_task_from_capture(source_type: str, source_id: str) -> Any:
        board = _board_store(app).load()
        title = ""
        summary = ""
        labels = ["captured"]
        owner = "PUXAI"

        if source_type == "note":
            note = next((item for item in board.get("notes", []) if item["id"] == source_id), None)
            if note is None:
                flash("Note not found.", "warning")
                return redirect(url_for("index"))
            title = note["title"]
            summary = note["body"]
            labels.append("note")
        elif source_type == "todo":
            todo_item = next((item for item in board.get("todo_items", []) if item["id"] == source_id), None)
            if todo_item is None:
                flash("Todo item not found.", "warning")
                return redirect(url_for("index"))
            title = todo_item["text"][:100]
            summary = f"Task created from todo inbox item:\n\n- {todo_item['text']}"
            labels.append("todo")
        else:
            flash("Unknown capture type.", "warning")
            return redirect(url_for("index"))

        task = _build_task_payload(
            board=board,
            title=title or "Captured task",
            summary=summary,
            status=board["statuses"][0],
            priority="Medium",
            labels=labels,
            owner=owner,
            ai_enrich=config.enable_ai,
            config=config,
        )
        _board_store(app).add_task(task)
        _append_activity_event(
            app,
            scope="task",
            task_id=task["id"],
            kind="task.created_from_capture",
            title="Task created from capture",
            summary=f"Created task '{task['title']}' from {source_type}.",
            payload={"source_type": source_type, "source_id": source_id},
        )
        _refresh_mermaid(app)
        flash(f"Created task '{task['title']}' from {source_type}.", "success")
        return redirect(url_for("edit_task", task_id=task["id"]))

    @app.post("/tasks/<task_id>/move")
    def move_task(task_id: str) -> Any:
        board = _board_store(app).load()
        status = request.form.get("status", "").strip()
        if status not in board["statuses"]:
            flash("Unknown status.", "warning")
            return redirect(url_for("index"))
        task = _find_task(board, task_id)
        _move_task_to_status(app, task_id, status)
        if task is not None:
            _append_activity_event(
                app,
                scope="task",
                task_id=task_id,
                kind="task.moved",
                title="Task moved",
                summary=f"Moved task '{task['title']}' to {status}.",
                payload={"status": status},
            )
        return redirect(url_for("index"))

    @app.post("/api/tasks/<task_id>/move")
    def api_move_task(task_id: str) -> Any:
        board = _board_store(app).load()
        payload = request.get_json(force=True)
        status = str(payload.get("status", "")).strip()
        if status not in board["statuses"]:
            return jsonify({"ok": False, "message": "Unknown status."}), 400
        task = _find_task(board, task_id)
        _move_task_to_status(app, task_id, status)
        if task is not None:
            _append_activity_event(
                app,
                scope="task",
                task_id=task_id,
                kind="task.moved",
                title="Task moved",
                summary=f"Moved task '{task['title']}' to {status}.",
                payload={"status": status},
            )
        return jsonify({"ok": True, "status": status})

    @app.post("/tasks/<task_id>/artifacts")
    def update_task_artifacts(task_id: str) -> Any:
        board = _board_store(app).load()
        task = _find_task(board, task_id)
        if task is None:
            flash("Task not found.", "warning")
            return redirect(url_for("index"))
        artifacts = {
            "architecture": request.form.get("architecture", "").strip(),
            "flow": request.form.get("flow", "").strip(),
            "kanban_subview": request.form.get("kanban_subview", "").strip(),
        }
        _board_store(app).update_task(task_id, {"mermaid_artifacts": {**task["mermaid_artifacts"], **artifacts}})
        _refresh_mermaid(app)
        flash(f"Saved Mermaid artifacts for '{task['title']}'.", "success")
        return redirect(url_for("index"))

    @app.post("/tasks/<task_id>/edit")
    def save_task_edit(task_id: str) -> Any:
        board = _board_store(app).load()
        task = _find_task(board, task_id)
        if task is None:
            flash("Task not found.", "warning")
            return redirect(url_for("index"))

        labels = [item.strip() for item in request.form.get("labels", "").split(",") if item.strip()]
        patch = {
            "title": request.form.get("title", task["title"]).strip() or task["title"],
            "summary": request.form.get("summary", task["summary"]).strip(),
            "status": request.form.get("status", task["status"]).strip(),
            "priority": request.form.get("priority", task["priority"]).strip(),
            "owner": request.form.get("owner", task["owner"]).strip() or task["owner"],
            "labels": labels,
            "notes": request.form.get("notes", task.get("notes", "")).strip(),
            "agent_brief": request.form.get("agent_brief", task.get("agent_brief", "")).strip(),
            "checklist": _parse_checklist_text(request.form.get("checklist_text", "")),
            "mermaid_artifacts": {
                "architecture": request.form.get("architecture", task["mermaid_artifacts"].get("architecture", "")).strip(),
                "flow": request.form.get("flow", task["mermaid_artifacts"].get("flow", "")).strip(),
                "kanban_subview": request.form.get("kanban_subview", task["mermaid_artifacts"].get("kanban_subview", "")).strip(),
                "sequence": request.form.get("sequence", task["mermaid_artifacts"].get("sequence", "")).strip(),
                "mindmap": request.form.get("mindmap", task["mermaid_artifacts"].get("mindmap", "")).strip(),
            },
        }
        if patch["status"] not in board["statuses"]:
            patch["status"] = task["status"]
        _board_store(app).update_task(task_id, patch)
        _append_activity_event(
            app,
            scope="task",
            task_id=task_id,
            kind="task.edited",
            title="Task edited",
            summary=f"Saved task workspace for '{patch['title']}'.",
            payload={"status": patch["status"], "priority": patch["priority"]},
        )
        _refresh_mermaid(app)
        flash(f"Saved task workspace for '{patch['title']}'.", "success")
        return redirect(url_for("edit_task", task_id=task_id))

    @app.post("/tasks/<task_id>/delete")
    def delete_task(task_id: str) -> Any:
        board = _board_store(app).load()
        task = _find_task(board, task_id)
        if task is None:
            flash("Task not found.", "warning")
            return redirect(url_for("index"))

        task_files_dir = _task_files_dir(app, task_id)
        if task_files_dir.exists():
            shutil.rmtree(task_files_dir, ignore_errors=True)

        _append_activity_event(
            app,
            scope="task",
            task_id=task_id,
            kind="task.deleted",
            title="Task deleted",
            summary=f"Deleted task '{task['title']}'.",
            payload={"title": task["title"]},
        )
        _board_store(app).delete_task(task_id)
        _refresh_mermaid(app)
        flash(f"Deleted task '{task['title']}'.", "success")
        return redirect(url_for("index"))

    @app.post("/tasks/<task_id>/repo-context")
    def update_repo_context(task_id: str) -> Any:
        board = _board_store(app).load()
        task = _find_task(board, task_id)
        if task is None:
            flash("Task not found.", "warning")
            return redirect(url_for("index"))
        repo_path = request.form.get("repo_path", "").strip()
        focus_patterns = request.form.get("focus_patterns", "").strip() or "*.py,*.md,*.json"
        notes = request.form.get("repo_notes", "").strip()
        if not repo_path:
            flash("Repository path is required to ingest context.", "warning")
            return redirect(url_for("index"))
        try:
            context = ingest_repository_context(repo_path, focus_patterns, notes)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Repo context ingestion failed")
            flash(f"Repo context ingestion failed: {exc}", "danger")
            return redirect(url_for("index"))
        _board_store(app).update_task(task_id, {"repo_context": context})
        _append_activity_event(
            app,
            scope="task",
            task_id=task_id,
            kind="task.repo_context_ingested",
            title="Repository context ingested",
            summary=f"Ingested repo context for '{task['title']}'.",
            payload={"repo_path": context.get("repo_path", "")},
        )
        _refresh_mermaid(app)
        flash(f"Ingested repo context for '{task['title']}'.", "success")
        return redirect(request.form.get("next") or url_for("index"))

    @app.post("/tasks/<task_id>/upload")
    def upload_task_file(task_id: str) -> Any:
        board = _board_store(app).load()
        task = _find_task(board, task_id)
        if task is None:
            flash("Task not found.", "warning")
            return redirect(url_for("index"))
        uploaded = request.files.get("attachment")
        if uploaded is None or not uploaded.filename:
            flash("Choose a file to attach.", "warning")
            return redirect(url_for("edit_task", task_id=task_id))
        filename = secure_filename(uploaded.filename)
        if not filename:
            flash("Attachment filename was not valid.", "warning")
            return redirect(url_for("edit_task", task_id=task_id))
        task_dir = _task_files_dir(app, task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        destination = task_dir / filename
        uploaded.save(destination)
        attachments = list(task.get("attachments", []))
        attachments.append(
            {
                "filename": filename,
                "stored_path": str(destination),
                "size_bytes": destination.stat().st_size,
                "uploaded_at": utc_now(),
            }
        )
        _board_store(app).update_task(task_id, {"attachments": attachments})
        _append_activity_event(
            app,
            scope="task",
            task_id=task_id,
            kind="task.file_attached",
            title="File attached",
            summary=f"Attached file '{filename}' to '{task['title']}'.",
            payload={"filename": filename, "size_bytes": destination.stat().st_size},
        )
        flash(f"Attached {filename}.", "success")
        return redirect(url_for("edit_task", task_id=task_id))

    @app.get("/tasks/<task_id>/files/<filename>")
    def task_file_download(task_id: str, filename: str) -> Any:
        task_dir = _task_files_dir(app, task_id)
        return send_from_directory(task_dir, filename, as_attachment=True)

    @app.post("/tasks/<task_id>/email-draft")
    def create_email_draft(task_id: str) -> Any:
        board = _board_store(app).load()
        task = _find_task(board, task_id)
        if task is None:
            flash("Task not found.", "warning")
            return redirect(url_for("index"))
        draft_type = request.form.get("draft_type", "work_brief").strip() or "work_brief"
        recipient = request.form.get("recipient", "").strip()
        draft = _create_email_draft_record(task, draft_type, recipient)
        drafts = list(task.get("email_drafts", []))
        drafts.insert(0, draft)
        _board_store(app).update_task(task_id, {"email_drafts": drafts[:10]})
        _append_activity_event(
            app,
            scope="task",
            task_id=task_id,
            kind="task.email_draft_created",
            title="Email draft created",
            summary=f"Created {_draft_type_label(draft_type)} draft for '{task['title']}'.",
            payload={"draft_type": _normalize_draft_type(draft_type), "recipient": recipient},
        )
        flash(f"Created {_draft_type_label(draft_type)} draft for '{task['title']}'.", "success")
        return redirect(url_for("edit_task", task_id=task_id))

    @app.get("/tasks/<task_id>/work-brief-download")
    def download_work_brief(task_id: str) -> Any:
        board = _board_store(app).load()
        task = _find_task(board, task_id)
        if task is None:
            abort(404)
        content = _build_work_brief_markdown(task)
        return send_file(
            BytesIO(content.encode("utf-8")),
            as_attachment=True,
            download_name=f"{secure_filename(task['title']) or 'task'}-work-brief.md",
            mimetype="text/markdown",
        )

    @app.post("/tasks/<task_id>/executor")
    def run_executor(task_id: str) -> Any:
        board = _board_store(app).load()
        task = _find_task(board, task_id)
        if task is None:
            flash("Task not found.", "warning")
            return redirect(url_for("index"))
        action = request.form.get("action", "").strip()
        metadata = get_executor_action_metadata(action)
        confirmed = request.form.get("confirm_run") == "1"
        if metadata.get("requires_confirmation") and not confirmed:
            flash(f"{metadata['label']} requires confirmation before it can run.", "warning")
            return redirect(request.form.get("next") or url_for("edit_task", task_id=task_id))
        try:
            result = execute_task_action(task, action)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Executor action failed")
            flash(f"Executor action failed: {exc}", "danger")
            return redirect(url_for("index"))

        patch = dict(result.get("task_patch", {}))
        if patch:
            _board_store(app).update_task(task_id, patch)
        run = record_executor_run(task_id, action, result.get("summary", action), result)
        _board_store(app).append_task_run(task_id, run)
        _board_store(app).append_agent_run(run)
        _append_activity_event(
            app,
            scope="task",
            task_id=task_id,
            kind="task.executor_completed",
            title="Executor action completed",
            summary=result.get("summary", f"Executed {action}."),
            payload={"action": action},
        )
        _refresh_mermaid(app)
        flash(result.get("summary", f"Executed {action}."), "success")
        return redirect(request.form.get("next") or url_for("index"))

    @app.post("/tasks/<task_id>/agent")
    def task_agent(task_id: str) -> Any:
        board = _board_store(app).load()
        task = _find_task(board, task_id)
        if task is None:
            flash("Task not found.", "warning")
            return redirect(url_for("index"))

        client = _ai_backend(config)
        if not client or not client.is_available():
            flash("The configured AI backend is not reachable, so the agent run could not start.", "warning")
            return redirect(url_for("index"))

        payload = run_task_agent(client, config.ollama_agent_model, board, task)
        if not payload:
            flash("The agent could not produce a structured result this time.", "warning")
            return redirect(url_for("index"))

        suggested_status = payload.get("status_suggestion", task["status"])
        if suggested_status not in board["statuses"]:
            suggested_status = task["status"]
        checklist = [
            {"text": str(item).strip(), "done": False}
            for item in payload.get("checklist", [])
            if str(item).strip()
        ] or task.get("checklist", [])
        merged_labels = sorted(
            {
                *task.get("labels", []),
                *[str(label).strip() for label in payload.get("labels", []) if str(label).strip()],
            }
        )
        artifact_patch = payload.get("mermaid_artifacts", {}) or {}
        notes = payload.get("notes", "")
        executor_action = str(payload.get("executor_action", "")).strip()
        _board_store(app).update_task(
            task_id,
            {
                "status": suggested_status,
                "summary": payload.get("summary", task["summary"]),
                "checklist": checklist,
                "labels": merged_labels,
                "mermaid_artifacts": {**task.get("mermaid_artifacts", {}), **artifact_patch},
                "latest_agent_notes": notes,
                "agent_brief": payload.get("next_step", task.get("agent_brief", "")),
                "last_executor_action": executor_action if executor_action and executor_action != "none" else task.get("last_executor_action", ""),
            },
        )
        run = record_agent_run(task_id, "task-agent", payload.get("summary", task["title"]), payload)
        _board_store(app).append_agent_run(run)
        _append_activity_event(
            app,
            scope="task",
            task_id=task_id,
            kind="task.agent_completed",
            title="Agent run completed",
            summary=payload.get("summary", f"Agent run completed for '{task['title']}'."),
            payload={"status_suggestion": suggested_status, "executor_action": executor_action},
        )
        _refresh_mermaid(app)
        flash(f"Agent run completed for '{task['title']}'.", "success")
        return redirect(request.form.get("next") or url_for("index"))

    @app.post("/tasks/<task_id>/toggle-check")
    def toggle_check(task_id: str) -> Any:
        board = _board_store(app).load()
        item_index = int(request.form.get("item_index", "-1"))
        task = _find_task(board, task_id)
        if task is None or item_index < 0 or item_index >= len(task.get("checklist", [])):
            flash("Checklist item not found.", "warning")
            return redirect(url_for("index"))
        checklist = list(task["checklist"])
        checklist[item_index]["done"] = not checklist[item_index].get("done", False)
        _board_store(app).update_task(task_id, {"checklist": checklist})
        item = checklist[item_index]
        _append_activity_event(
            app,
            scope="task",
            task_id=task_id,
            kind="task.checklist_toggled",
            title="Checklist updated",
            summary=f"{'Completed' if item.get('done') else 'Reopened'} checklist item '{item.get('text', '')}'.",
            payload={"item_index": item_index, "done": item.get("done", False)},
        )
        return redirect(url_for("index"))

    @app.post("/launch/<app_id>")
    def launch_app(app_id: str) -> Any:
        if launcher is None:
            flash("No launcher is available on this operating system.", "warning")
            return redirect(url_for("index"))
        try:
            launched = launcher.launch_app(app_id)
            append_launch_event(history_file, launched)
            flash(f"Launched {launched.name}.", "success")
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Failed to launch %s", app_id)
            flash(f"Launch failed: {exc}", "danger")
        return redirect(url_for("index"))

    @app.post("/board/summary")
    def update_summary() -> Any:
        board = _board_store(app).load()
        summary = request.form.get("board_summary", "").strip()
        ideas_text = request.form.get("ideas", "").strip()
        board["board_summary"] = summary or board["board_summary"]
        board["ideas"] = [line.strip() for line in ideas_text.splitlines() if line.strip()]
        _board_store(app).save(board)
        _append_activity_event(
            app,
            scope="board",
            kind="board.summary_updated",
            title="Board narrative updated",
            summary="Saved board summary and ideas.",
        )
        _refresh_mermaid(app)
        flash("Board narrative updated.", "success")
        return redirect(url_for("index"))

    @app.post("/board/refresh-mermaid")
    def refresh_mermaid() -> Any:
        _refresh_mermaid(app)
        _append_activity_event(
            app,
            scope="board",
            kind="board.mermaid_refreshed",
            title="Mermaid refreshed",
            summary="Refreshed board Mermaid views.",
        )
        flash("Board Mermaid views refreshed.", "success")
        return redirect(url_for("index"))

    @app.post("/api/chat")
    def api_chat() -> Any:
        payload = request.get_json(force=True)
        message = (payload.get("message") or "").strip()
        if not message:
            return jsonify({"ok": False, "message": "Message is required."}), 400
        board = _board_store(app).load()
        client = _ai_backend(config)
        action_results: list[dict[str, Any]] = []
        if not client or not client.is_available():
            reply = (
                "The configured AI backend is not reachable right now. "
                "Check `config.ini` and start the backend, then try again."
            )
        else:
            try:
                plan = board_chat_action_plan(client, config.ollama_model, board, message)
                if plan and isinstance(plan.get("actions"), list):
                    reply = str(plan.get("reply", "")).strip() or "I completed the requested actions."
                    action_results = _execute_chat_actions(app, config, plan.get("actions", []))
                    if action_results:
                        action_lines = "\n".join(
                            f"- {result['summary']}"
                            for result in action_results
                        )
                        reply = f"{reply}\n\nCompleted actions:\n{action_lines}"
                else:
                    reply = board_chat_reply(client, config.ollama_model, board, message)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Chat request failed")
                reply = f"The assistant hit an error while contacting the AI backend: {exc}"
        user_message = {"role": "user", "content": message, "created_at": utc_now()}
        assistant_message = {"role": "assistant", "content": reply, "created_at": utc_now()}
        _board_store(app).append_chat_message(user_message)
        _board_store(app).append_chat_message(assistant_message)
        return jsonify(
            {
                "ok": True,
                "reply": reply,
                "actions": action_results,
                "refresh_board": any(result.get("ok") for result in action_results),
                "history": board.get("chat_history", []) + [user_message, assistant_message],
            }
        )

    @app.get("/api/ai/status")
    def api_ai_status() -> Any:
        return jsonify(_ai_status(config))

    @app.get("/api/ollama/status")
    def api_ollama_status() -> Any:
        return jsonify(_ai_status(config))

    return app


def _board_store(app: Flask) -> BoardStore:
    return app.config["BOARD_STORE"]


def _ai_backend(config: AppConfig):
    return create_ai_backend(config)


def _ai_status(config: AppConfig) -> dict[str, Any]:
    client = _ai_backend(config)
    backend_name = str(config.ai_backend).strip().lower() or "ollama"
    backend_url = config.ollama_url if backend_name == "ollama" else "n/a"
    status = {
        "backend": backend_name,
        "available": False,
        "models": [],
        "default_model": config.ollama_model,
        "agent_model": config.ollama_agent_model,
        "url": backend_url,
    }
    if client is None:
        return status
    try:
        status["models"] = client.list_models()
        status["available"] = client.is_available()
        return status
    except Exception:  # noqa: BLE001
        return status


def _settings_checkbox(form: Any, name: str, current_value: bool) -> bool:
    if name in form:
        return form.get(name) == "1"
    return current_value


def _settings_preview_config(form: Any, current: AppConfig) -> AppConfig:
    return AppConfig(
        app_name=str(form.get("app_name", current.app_name)).strip() or current.app_name,
        data_dir=str(form.get("data_dir", current.data_dir)).strip() or current.data_dir,
        default_workspace=str(form.get("default_workspace", current.default_workspace)).strip() or current.default_workspace,
        workspace_default_id=current.workspace_default_id,
        enable_ai=_settings_checkbox(form, "enable_ai", current.enable_ai),
        ai_backend=str(form.get("ai_backend", current.ai_backend)).strip() or current.ai_backend,
        enable_tasks=_settings_checkbox(form, "enable_tasks", current.enable_tasks),
        enable_notes=_settings_checkbox(form, "enable_notes", current.enable_notes),
        enable_outlook=_settings_checkbox(form, "enable_outlook", current.enable_outlook),
        enable_history_panel=_settings_checkbox(form, "enable_history_panel", current.enable_history_panel),
        enable_tray_icon=_settings_checkbox(form, "enable_tray_icon", current.enable_tray_icon),
        window_mode=current.window_mode,
        transparent_background=current.transparent_background,
        web_host=str(form.get("web_host", current.web_host)).strip() or current.web_host,
        web_port=_parse_int_or_default(form.get("web_port", current.web_port), current.web_port),
        web_debug=current.web_debug,
        auto_open_browser=_settings_checkbox(form, "auto_open_browser", current.auto_open_browser),
        open_browser_delay_seconds=current.open_browser_delay_seconds,
        ollama_url=str(form.get("ollama_url", current.ollama_url)).strip() or current.ollama_url,
        ollama_model=str(form.get("ollama_model", current.ollama_model)).strip() or current.ollama_model,
        ollama_request_timeout_seconds=_parse_int_or_default(
            form.get("ollama_request_timeout_seconds", current.ollama_request_timeout_seconds),
            current.ollama_request_timeout_seconds,
        ),
        ollama_agent_model=str(form.get("ollama_agent_model", current.ollama_agent_model)).strip() or current.ollama_agent_model,
        chatgpt_api_key_env_var=current.chatgpt_api_key_env_var,
        chatgpt_model=current.chatgpt_model,
        chatgpt_timeout_seconds=current.chatgpt_timeout_seconds,
        copilot_enabled=current.copilot_enabled,
        copilot_tenant_id=current.copilot_tenant_id,
        copilot_client_id=current.copilot_client_id,
        copilot_client_secret_env_var=current.copilot_client_secret_env_var,
        outlook_enabled=_settings_checkbox(form, "enable_outlook", current.outlook_enabled),
        outlook_default_task_folder=current.outlook_default_task_folder,
        outlook_read_inbox_folder=current.outlook_read_inbox_folder,
        outlook_max_emails=current.outlook_max_emails,
    )


def _build_settings_config_from_form(req: Any, current: AppConfig) -> AppConfig:
    form = req.form
    app_name = str(form.get("app_name", "")).strip()
    if not app_name:
        raise ValueError("App name cannot be empty.")

    data_dir = str(form.get("data_dir", "")).strip()
    if not data_dir:
        raise ValueError("Data directory cannot be empty.")

    default_workspace = str(form.get("default_workspace", "")).strip()
    if not default_workspace:
        raise ValueError("Default workspace cannot be empty.")

    ai_backend = str(form.get("ai_backend", current.ai_backend)).strip().lower() or current.ai_backend
    if ai_backend not in {"ollama", "dummy", "openai", "azure_openai", "copilot"}:
        raise ValueError("Choose a valid AI backend.")

    web_host = str(form.get("web_host", "")).strip()
    if not web_host:
        raise ValueError("Web host cannot be empty.")

    web_port = _parse_int(form.get("web_port", ""))
    if web_port < 1 or web_port > 65535:
        raise ValueError("Web port must be between 1 and 65535.")

    request_timeout = _parse_int(form.get("ollama_request_timeout_seconds", ""))
    if request_timeout < 1:
        raise ValueError("Request timeout must be a positive integer.")

    ollama_url = str(form.get("ollama_url", "")).strip()
    if not ollama_url:
        raise ValueError("Ollama URL cannot be empty.")

    ollama_model = str(form.get("ollama_model", "")).strip()
    if not ollama_model:
        raise ValueError("Ollama default model cannot be empty.")

    ollama_agent_model = str(form.get("ollama_agent_model", "")).strip()
    if not ollama_agent_model:
        raise ValueError("Ollama agent model cannot be empty.")

    return AppConfig(
        app_name=app_name,
        data_dir=data_dir,
        default_workspace=default_workspace,
        workspace_default_id=current.workspace_default_id,
        enable_ai=form.get("enable_ai") == "1",
        ai_backend=ai_backend,
        enable_tasks=form.get("enable_tasks") == "1",
        enable_notes=form.get("enable_notes") == "1",
        enable_outlook=form.get("enable_outlook") == "1",
        enable_history_panel=form.get("enable_history_panel") == "1",
        enable_tray_icon=form.get("enable_tray_icon") == "1",
        window_mode=current.window_mode,
        transparent_background=current.transparent_background,
        web_host=web_host,
        web_port=web_port,
        web_debug=current.web_debug,
        auto_open_browser=form.get("auto_open_browser") == "1",
        open_browser_delay_seconds=current.open_browser_delay_seconds,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        ollama_request_timeout_seconds=request_timeout,
        ollama_agent_model=ollama_agent_model,
        chatgpt_api_key_env_var=current.chatgpt_api_key_env_var,
        chatgpt_model=current.chatgpt_model,
        chatgpt_timeout_seconds=current.chatgpt_timeout_seconds,
        copilot_enabled=current.copilot_enabled,
        copilot_tenant_id=current.copilot_tenant_id,
        copilot_client_id=current.copilot_client_id,
        copilot_client_secret_env_var=current.copilot_client_secret_env_var,
        outlook_enabled=form.get("enable_outlook") == "1",
        outlook_default_task_folder=current.outlook_default_task_folder,
        outlook_read_inbox_folder=current.outlook_read_inbox_folder,
        outlook_max_emails=current.outlook_max_emails,
    )


def _parse_int(raw_value: Any) -> int:
    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("Enter a valid whole number.") from exc


def _parse_int_or_default(raw_value: Any, default: int) -> int:
    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError):
        return default


def _tasks_by_status(board: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped = {status: [] for status in board["statuses"]}
    for task in board["tasks"]:
        grouped.setdefault(task["status"], []).append(task)
    return grouped


def _find_task(board: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    return next((item for item in board.get("tasks", []) if item["id"] == task_id), None)


def _find_note(board: dict[str, Any], note_id: str) -> dict[str, Any] | None:
    return next((item for item in board.get("notes", []) if item["id"] == note_id), None)


def _find_todo_item(board: dict[str, Any], todo_id: str) -> dict[str, Any] | None:
    return next((item for item in board.get("todo_items", []) if item["id"] == todo_id), None)


def _match_by_text(
    items: list[dict[str, Any]],
    field_name: str,
    value: str,
) -> dict[str, Any] | None:
    target = value.strip().casefold()
    if not target:
        return None
    exact_matches = [
        item for item in items
        if str(item.get(field_name, "")).strip().casefold() == target
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]

    partial_matches = [
        item for item in items
        if target in str(item.get(field_name, "")).strip().casefold()
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]
    return None


def _resolve_task(board: dict[str, Any], args: dict[str, Any]) -> dict[str, Any] | None:
    task_id = str(args.get("task_id", "")).strip()
    if task_id:
        task = _find_task(board, task_id)
        if task is not None:
            return task
    task_title = str(args.get("task_title", "")).strip() or str(args.get("title", "")).strip()
    return _match_by_text(board.get("tasks", []), "title", task_title)


def _resolve_note(board: dict[str, Any], args: dict[str, Any]) -> dict[str, Any] | None:
    note_id = str(args.get("note_id", "")).strip()
    if note_id:
        note = _find_note(board, note_id)
        if note is not None:
            return note
    note_title = str(args.get("note_title", "")).strip() or str(args.get("title", "")).strip()
    return _match_by_text(board.get("notes", []), "title", note_title)


def _resolve_todo_item(board: dict[str, Any], args: dict[str, Any]) -> dict[str, Any] | None:
    todo_id = str(args.get("todo_id", "")).strip()
    if todo_id:
        todo_item = _find_todo_item(board, todo_id)
        if todo_item is not None:
            return todo_item
    todo_text = str(args.get("todo_text", "")).strip() or str(args.get("text", "")).strip()
    return _match_by_text(board.get("todo_items", []), "text", todo_text)


def _task_files_dir(app: Flask, task_id: str) -> Path:
    return _board_store(app).current_workspace_root() / "task_files" / task_id


def _append_activity_event(
    app: Flask,
    *,
    scope: str,
    kind: str,
    title: str,
    summary: str,
    task_id: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    _board_store(app).append_activity_event(
        {
            "id": new_id(),
            "scope": scope,
            "task_id": task_id,
            "kind": kind,
            "title": title,
            "summary": summary,
            "payload": payload or {},
            "created_at": utc_now(),
        }
    )


def _task_executor_action_details(task: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        preview_task_action(task, action)
        for action in task.get("executor_actions", [])
        if action
    ]


def _checklist_to_text(items: list[dict[str, Any]]) -> str:
    lines = []
    for item in items:
        marker = "x" if item.get("done") else " "
        lines.append(f"- [{marker}] {item.get('text', '').strip()}")
    return "\n".join(lines)


def _build_task_payload(
    *,
    board: dict[str, Any],
    title: str,
    summary: str,
    status: str,
    priority: str,
    labels: list[str],
    owner: str,
    ai_enrich: bool,
    config: AppConfig,
) -> dict[str, Any]:
    task = {
        "id": new_id(),
        "title": title,
        "summary": summary,
        "status": status if status in board["statuses"] else board["statuses"][0],
        "priority": priority,
        "labels": labels,
        "owner": owner,
        "checklist": [],
        "agent_brief": "",
        "latest_agent_notes": "",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "mermaid_artifacts": default_mermaid_artifacts(),
        "repo_context": default_repo_context(),
        "executor_runs": [],
        "last_executor_action": "",
        "last_executor_notes": "",
    }

    if ai_enrich and config.enable_ai:
        client = _ai_backend(config)
        if client and client.is_available():
            ai_payload = draft_task_with_ai(client, config.ollama_agent_model, board, title, summary)
            if ai_payload:
                task["summary"] = ai_payload.get("summary", task["summary"])
                task["priority"] = ai_payload.get("priority", task["priority"])
                task["labels"] = sorted(
                    {
                        *task["labels"],
                        *[label for label in ai_payload.get("labels", []) if label],
                    }
                )
                task["owner"] = ai_payload.get("owner", task["owner"]) or task["owner"]
                task["checklist"] = [
                    {"text": str(item).strip(), "done": False}
                    for item in ai_payload.get("checklist", [])
                    if str(item).strip()
                ]
                task["agent_brief"] = ai_payload.get("agent_brief", "")
                task["mermaid_artifacts"] = {
                    **task["mermaid_artifacts"],
                    **(ai_payload.get("mermaid_artifacts", {}) or {}),
                }
                task["repo_context"]["notes"] = str(ai_payload.get("repo_context_notes", "")).strip()
    return task


def _parse_checklist_text(raw_text: str) -> list[dict[str, Any]]:
    checklist: list[dict[str, Any]] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        done = line.startswith("- [x]") or line.startswith("* [x]") or line.startswith("[x]")
        cleaned = (
            line.replace("- [x]", "")
            .replace("- [ ]", "")
            .replace("* [x]", "")
            .replace("* [ ]", "")
            .replace("[x]", "")
            .replace("[ ]", "")
            .strip()
        )
        if cleaned:
            checklist.append({"text": cleaned, "done": done})
    return checklist


def _draft_subject(task: dict[str, Any], draft_type: str) -> str:
    normalized = _normalize_draft_type(draft_type)
    if normalized == "work_brief":
        return f"Work Brief: {task['title']}"
    if draft_type == "status":
        return f"Status update: {task['title']}"
    return f"PUXAI task: {task['title']}"


def _draft_body(task: dict[str, Any], draft_type: str) -> str:
    normalized = _normalize_draft_type(draft_type)
    selected_files = task.get("repo_context", {}).get("selected_files", [])[:5]
    file_list = "\n".join(f"- {path}" for path in selected_files) or "- No files linked yet"
    checklist_text = "\n".join(
        f"- {item['text']}" for item in task.get("checklist", []) if item.get("text")
    ) or "- No checklist items yet"
    if normalized == "status":
        return (
            f"Task: {task['title']}\n\n"
            f"Summary:\n{task.get('summary', '')}\n\n"
            f"Status: {task.get('status', '')}\n"
            f"Priority: {task.get('priority', '')}\n\n"
            f"Checklist:\n{checklist_text}\n\n"
            f"Notes:\n{task.get('notes', '')}"
        )
    return (
        f"Hello,\n\n"
        f"We would like to request information/quotation support for the following task:\n\n"
        f"Task: {task['title']}\n"
        f"Summary: {task.get('summary', '')}\n\n"
        f"Linked files:\n{file_list}\n\n"
        f"Requested actions:\n{checklist_text}\n\n"
        f"Notes:\n{task.get('notes', '')}\n\n"
        "Thanks."
    )


def _create_email_draft_record(task: dict[str, Any], draft_type: str, recipient: str) -> dict[str, Any]:
    normalized = _normalize_draft_type(draft_type)
    return {
        "id": new_id(),
        "type": normalized,
        "recipient": recipient,
        "subject": _draft_subject(task, normalized),
        "body": _draft_body(task, normalized),
        "created_at": utc_now(),
    }


def _build_work_brief_markdown(task: dict[str, Any]) -> str:
    artifacts = task.get("mermaid_artifacts", {})
    attachments = task.get("attachments", [])
    files = "\n".join(f"- {item['filename']}" for item in attachments) or "- No attachments"
    checklist = "\n".join(
        f"- [{'x' if item.get('done') else ' '}] {item.get('text', '')}" for item in task.get("checklist", [])
    ) or "- No checklist items"
    return (
        f"# Work Brief: {task['title']}\n\n"
        f"## Summary\n{task.get('summary', '')}\n\n"
        f"## Status\n- Status: {task.get('status', '')}\n- Priority: {task.get('priority', '')}\n- Owner: {task.get('owner', '')}\n\n"
        f"## Notes\n{task.get('notes', '') or 'No notes'}\n\n"
        f"## Checklist\n{checklist}\n\n"
        f"## Attachments\n{files}\n\n"
        f"## Mermaid Flow\n```mermaid\n{artifacts.get('flow', '')}\n```\n"
    )


def _normalize_draft_type(draft_type: str) -> str:
    normalized = str(draft_type).strip().lower()
    if normalized == "rfq":
        return "work_brief"
    if normalized == "status":
        return "status"
    if normalized == "work brief":
        return "work_brief"
    return normalized or "work_brief"


def _draft_type_label(draft_type: str) -> str:
    normalized = _normalize_draft_type(draft_type)
    if normalized == "work_brief":
        return "Work Brief"
    if normalized == "status":
        return "Status Update"
    return normalized.replace("_", " ").title()


def _move_task_to_status(app: Flask, task_id: str, status: str) -> None:
    _board_store(app).update_task(task_id, {"status": status})
    _refresh_mermaid(app)


def _refresh_mermaid(app: Flask) -> None:
    board = _board_store(app).load()
    board["board_mermaid_artifacts"] = {
        "kanban": build_kanban_mermaid(board),
        "stitched": build_stitched_board_mermaid(board),
    }
    _board_store(app).save(board)


def _render_markdown(raw_text: str) -> Markup:
    text = (raw_text or "").strip()
    if not text:
        return Markup("")

    if markdown_lib is not None:
        html = markdown_lib.markdown(
            text,
            extensions=["extra", "sane_lists", "nl2br"],
        )
        return Markup(html)

    escaped = escape(text)
    html = str(escaped)
    html = re.sub(r"(?m)^### (.+)$", r"<h3>\1</h3>", html)
    html = re.sub(r"(?m)^## (.+)$", r"<h2>\1</h2>", html)
    html = re.sub(r"(?m)^# (.+)$", r"<h1>\1</h1>", html)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    html = re.sub(r"`(.+?)`", r"<code>\1</code>", html)
    blocks = [block.strip() for block in html.split("\n\n") if block.strip()]
    rendered_blocks: list[str] = []
    for block in blocks:
        lines = block.splitlines()
        if all(line.startswith("- ") for line in lines):
            items = "".join(f"<li>{line[2:]}</li>" for line in lines)
            rendered_blocks.append(f"<ul>{items}</ul>")
        elif all(line.startswith("1. ") for line in lines):
            items = "".join(f"<li>{line[3:]}</li>" for line in lines)
            rendered_blocks.append(f"<ol>{items}</ol>")
        elif block.startswith("<h1>") or block.startswith("<h2>") or block.startswith("<h3>"):
            rendered_blocks.append(block)
        else:
            rendered_blocks.append(f"<p>{'<br>'.join(lines)}</p>")
    return Markup("".join(rendered_blocks))


def _execute_chat_actions(
    app: Flask,
    config: AppConfig,
    actions: list[Any],
) -> list[dict[str, Any]]:
    executed: list[dict[str, Any]] = []
    for raw_action in actions[:6]:
        if not isinstance(raw_action, dict):
            continue
        name = str(raw_action.get("name", "")).strip()
        args = raw_action.get("args", {}) or {}
        if not isinstance(args, dict) or not name:
            continue
        try:
            result = _execute_chat_action(app, config, name, args)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Chat action failed: %s", name)
            executed.append({"name": name, "ok": False, "summary": f"{name} failed: {exc}"})
            continue
        executed.append({"name": name, "ok": True, **result})
    return executed


def _execute_chat_action(
    app: Flask,
    config: AppConfig,
    name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    board = _board_store(app).load()

    if name == "create_note":
        title = str(args.get("title", "")).strip() or "Untitled note"
        body = str(args.get("body", "")).strip()
        if not body:
            raise ValueError("Note body is required.")
        note = default_note()
        note.update({"title": title, "body": body, "updated_at": utc_now()})
        _board_store(app).add_note(note)
        _append_activity_event(
            app,
            scope="board",
            kind="note.created",
            title="Note created",
            summary=f"Saved note '{title}'.",
            payload={"note_id": note["id"]},
        )
        return {"summary": f"Created note '{title}'.", "note_id": note["id"]}

    if name == "create_todo":
        text = str(args.get("text", "")).strip()
        if not text:
            raise ValueError("Todo text is required.")
        todo_item = default_todo_item()
        todo_item.update({"text": text, "updated_at": utc_now()})
        _board_store(app).add_todo_item(todo_item)
        _append_activity_event(
            app,
            scope="board",
            kind="todo.created",
            title="Todo created",
            summary=f"Added todo '{text}'.",
            payload={"todo_id": todo_item["id"]},
        )
        return {"summary": f"Added todo '{text}'.", "todo_id": todo_item["id"]}

    if name == "create_task":
        title = str(args.get("title", "")).strip()
        if not title:
            raise ValueError("Task title is required.")
        task = _build_task_payload(
            board=board,
            title=title,
            summary=str(args.get("summary", "")).strip(),
            status=str(args.get("status", board["statuses"][0])).strip(),
            priority=str(args.get("priority", "Medium")).strip() or "Medium",
            labels=[str(label).strip() for label in args.get("labels", []) if str(label).strip()],
            owner=str(args.get("owner", "PUXAI")).strip() or "PUXAI",
            ai_enrich=bool(args.get("ai_enrich", True)),
            config=config,
        )
        _board_store(app).add_task(task)
        _append_activity_event(
            app,
            scope="task",
            task_id=task["id"],
            kind="task.created",
            title="Task created",
            summary=f"Created task '{task['title']}' in {task['status']}.",
            payload={"status": task["status"], "priority": task["priority"]},
        )
        _refresh_mermaid(app)
        return {"summary": f"Created task '{task['title']}'.", "task_id": task["id"]}

    if name == "create_task_from_note":
        note = _resolve_note(board, args)
        if note is None:
            raise ValueError("Note not found. Provide a note id or an exact note title.")
        task = _build_task_payload(
            board=board,
            title=note["title"],
            summary=note["body"],
            status=board["statuses"][0],
            priority="Medium",
            labels=["captured", "note"],
            owner="PUXAI",
            ai_enrich=True,
            config=config,
        )
        _board_store(app).add_task(task)
        _append_activity_event(
            app,
            scope="task",
            task_id=task["id"],
            kind="task.created_from_capture",
            title="Task created from note",
            summary=f"Created task '{task['title']}' from note.",
            payload={"source_type": "note", "source_id": note["id"]},
        )
        _refresh_mermaid(app)
        return {
            "summary": f"Created task '{task['title']}' from note.",
            "task_id": task["id"],
        }

    if name == "create_task_from_todo":
        todo_item = _resolve_todo_item(board, args)
        if todo_item is None:
            raise ValueError("Todo item not found. Provide a todo id or the exact todo text.")
        task = _build_task_payload(
            board=board,
            title=todo_item["text"][:100] or "Captured todo task",
            summary=f"Task created from todo inbox item:\n\n- {todo_item['text']}",
            status=board["statuses"][0],
            priority="Medium",
            labels=["captured", "todo"],
            owner="PUXAI",
            ai_enrich=True,
            config=config,
        )
        _board_store(app).add_task(task)
        _append_activity_event(
            app,
            scope="task",
            task_id=task["id"],
            kind="task.created_from_capture",
            title="Task created from todo",
            summary=f"Created task '{task['title']}' from todo.",
            payload={"source_type": "todo", "source_id": todo_item["id"]},
        )
        _refresh_mermaid(app)
        return {
            "summary": f"Created task '{task['title']}' from todo.",
            "task_id": task["id"],
        }

    if name == "create_email_draft":
        task = _resolve_task(board, args)
        if task is None:
            raise ValueError("Task not found. Provide a task id or an exact task title.")
        draft_type = str(args.get("draft_type", "rfq")).strip() or "rfq"
        recipient = str(args.get("recipient", "")).strip()
        draft = _create_email_draft_record(task, draft_type, recipient)
        drafts = list(task.get("email_drafts", []))
        drafts.insert(0, draft)
        _board_store(app).update_task(task["id"], {"email_drafts": drafts[:10]})
        _append_activity_event(
            app,
            scope="task",
            task_id=task["id"],
            kind="task.email_draft_created",
            title="Email draft created",
            summary=f"Created {_draft_type_label(draft_type)} draft for '{task['title']}'.",
            payload={"draft_type": _normalize_draft_type(draft_type), "recipient": recipient},
        )
        return {
            "summary": (
                f"Created {_draft_type_label(draft_type)} draft for '{task['title']}'. "
                "Open Edit on that task to view the draft."
            ),
            "task_id": task["id"],
        }

    if name == "update_task":
        task = _resolve_task(board, args)
        if task is None:
            raise ValueError("Task not found. Provide a task id or an exact task title.")
        task_id = task["id"]
        patch: dict[str, Any] = {}
        for key in ("title", "summary", "priority", "owner", "notes", "agent_brief"):
            if key in args:
                value = str(args.get(key, "")).strip()
                if value:
                    patch[key] = value
        if "status" in args:
            status = str(args.get("status", "")).strip()
            if status in board["statuses"]:
                patch["status"] = status
        if "labels" in args:
            patch["labels"] = [str(label).strip() for label in args.get("labels", []) if str(label).strip()]
        if patch:
            _board_store(app).update_task(task_id, patch)
            _append_activity_event(
                app,
                scope="task",
                task_id=task_id,
                kind="task.edited",
                title="Task edited",
                summary=f"Updated task '{task['title']}'.",
                payload=patch,
            )
            _refresh_mermaid(app)
        return {"summary": f"Updated task '{task['title']}'.", "task_id": task_id}

    if name == "move_task":
        status = str(args.get("status", "")).strip()
        task = _resolve_task(board, args)
        if task is None:
            raise ValueError("Task not found. Provide a task id or an exact task title.")
        if status not in board["statuses"]:
            raise ValueError("Status not found.")
        task_id = task["id"]
        _move_task_to_status(app, task_id, status)
        _append_activity_event(
            app,
            scope="task",
            task_id=task_id,
            kind="task.moved",
            title="Task moved",
            summary=f"Moved task '{task['title']}' to {status}.",
            payload={"status": status},
        )
        return {"summary": f"Moved task '{task['title']}' to {status}.", "task_id": task_id}

    if name == "run_executor":
        action = str(args.get("action", "")).strip()
        task = _resolve_task(board, args)
        if task is None:
            raise ValueError("Task not found. Provide a task id or an exact task title.")
        task_id = task["id"]
        metadata = get_executor_action_metadata(action)
        if metadata.get("requires_confirmation"):
            return {
                "summary": (
                    f"{metadata['label']} was not run because user confirmation is required. "
                    "Open the task workspace to review the preview and confirm it manually."
                ),
                "task_id": task_id,
            }
        result = execute_task_action(task, action)
        patch = dict(result.get("task_patch", {}))
        if patch:
            _board_store(app).update_task(task_id, patch)
        run = record_executor_run(task_id, action, result.get("summary", action), result)
        _board_store(app).append_task_run(task_id, run)
        _board_store(app).append_agent_run(run)
        _append_activity_event(
            app,
            scope="task",
            task_id=task_id,
            kind="task.executor_completed",
            title="Executor action completed",
            summary=result.get("summary", f"Executed {action}."),
            payload={"action": action},
        )
        _refresh_mermaid(app)
        return {"summary": result.get("summary", f"Executed {action}."), "task_id": task_id}

    raise ValueError(f"Unsupported chat action: {name}")
