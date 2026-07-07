"""Flask application for the PUXAI local workspace."""

from __future__ import annotations

from io import BytesIO
import logging
from pathlib import Path
import shutil
from typing import Any

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, send_from_directory, url_for
from werkzeug.utils import secure_filename

from app.config import AppConfig
from app.launchers import BaseLauncher
from app.session_history import append_launch_event
from app.services.agent_service import board_chat_reply, draft_task_with_ai, record_agent_run, run_task_agent
from app.services.board_store import BoardStore, default_mermaid_artifacts, default_repo_context, new_id, utc_now
from app.services.executor_service import execute_task_action, record_executor_run
from app.services.mermaid_service import build_kanban_mermaid, build_stitched_board_mermaid
from app.services.ollama_client import OllamaClient
from app.services.repo_context_service import ingest_repository_context

LOGGER = logging.getLogger(__name__)


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
    app.config["OS_NAME"] = os_name
    app.config["LAUNCHER"] = launcher
    app.config["HISTORY_FILE"] = history_file
    app.config["BOARD_STORE"] = BoardStore(config.data_dir)

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        board = _board_store(app).load()
        ollama_status = _ollama_status(config)
        return {
            "app_config": config,
            "os_name": os_name,
            "launchable_apps": launcher.list_apps() if launcher else [],
            "ollama_status": ollama_status,
            "board_kanban_mermaid": board.get("board_mermaid_artifacts", {}).get("kanban", ""),
            "board_stitched_mermaid": board.get("board_mermaid_artifacts", {}).get("stitched", ""),
        }

    @app.get("/")
    def index() -> str:
        board = _board_store(app).load()
        _refresh_mermaid(app)
        board = _board_store(app).load()
        return render_template(
            "index.html",
            board=board,
            tasks_by_status=_tasks_by_status(board),
            os_name=os_name,
        )

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
            client = _ollama_client(config)
            if client and client.is_available():
                ai_payload = draft_task_with_ai(client, config.ollama_agent_model, board, title, summary)
                if ai_payload:
                    task["summary"] = ai_payload.get("summary", task["summary"])
                    task["priority"] = ai_payload.get("priority", task["priority"])
                    task["labels"] = [label for label in ai_payload.get("labels", task["labels"]) if label]
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

        _board_store(app).add_task(task)
        _refresh_mermaid(app)
        flash(f"Added task '{title}'.", "success")
        return redirect(url_for("index"))

    @app.post("/tasks/<task_id>/move")
    def move_task(task_id: str) -> Any:
        board = _board_store(app).load()
        status = request.form.get("status", "").strip()
        if status not in board["statuses"]:
            flash("Unknown status.", "warning")
            return redirect(url_for("index"))
        _move_task_to_status(app, task_id, status)
        return redirect(url_for("index"))

    @app.post("/api/tasks/<task_id>/move")
    def api_move_task(task_id: str) -> Any:
        board = _board_store(app).load()
        payload = request.get_json(force=True)
        status = str(payload.get("status", "")).strip()
        if status not in board["statuses"]:
            return jsonify({"ok": False, "message": "Unknown status."}), 400
        _move_task_to_status(app, task_id, status)
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
        draft_type = request.form.get("draft_type", "rfq").strip() or "rfq"
        recipient = request.form.get("recipient", "").strip()
        subject = _draft_subject(task, draft_type)
        body = _draft_body(task, draft_type)
        drafts = list(task.get("email_drafts", []))
        drafts.insert(
            0,
            {
                "id": new_id(),
                "type": draft_type,
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "created_at": utc_now(),
            },
        )
        _board_store(app).update_task(task_id, {"email_drafts": drafts[:10]})
        flash(f"Created {draft_type.upper()} email draft for '{task['title']}'.", "success")
        return redirect(url_for("edit_task", task_id=task_id))

    @app.get("/tasks/<task_id>/rfq-download")
    def download_rfq_brief(task_id: str) -> Any:
        board = _board_store(app).load()
        task = _find_task(board, task_id)
        if task is None:
            abort(404)
        content = _build_rfq_markdown(task)
        return send_file(
            BytesIO(content.encode("utf-8")),
            as_attachment=True,
            download_name=f"{secure_filename(task['title']) or 'task'}-rfq.md",
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

        client = _ollama_client(config)
        if not client or not client.is_available():
            flash("Ollama is not reachable, so the agent run could not start.", "warning")
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
        _refresh_mermaid(app)
        flash("Board narrative updated.", "success")
        return redirect(url_for("index"))

    @app.post("/board/refresh-mermaid")
    def refresh_mermaid() -> Any:
        _refresh_mermaid(app)
        flash("Board Mermaid views refreshed.", "success")
        return redirect(url_for("index"))

    @app.post("/api/chat")
    def api_chat() -> Any:
        payload = request.get_json(force=True)
        message = (payload.get("message") or "").strip()
        if not message:
            return jsonify({"ok": False, "message": "Message is required."}), 400
        board = _board_store(app).load()
        client = _ollama_client(config)
        if not client or not client.is_available():
            reply = (
                "Ollama is not reachable right now. Start the Ollama server and model, "
                "then try again."
            )
        else:
            try:
                reply = board_chat_reply(client, config.ollama_model, board, message)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Chat request failed")
                reply = f"The assistant hit an error while contacting Ollama: {exc}"
        user_message = {"role": "user", "content": message, "created_at": utc_now()}
        assistant_message = {"role": "assistant", "content": reply, "created_at": utc_now()}
        _board_store(app).append_chat_message(user_message)
        _board_store(app).append_chat_message(assistant_message)
        return jsonify({"ok": True, "reply": reply, "history": board.get("chat_history", []) + [user_message, assistant_message]})

    @app.get("/api/ollama/status")
    def api_ollama_status() -> Any:
        return jsonify(_ollama_status(config))

    return app


def _board_store(app: Flask) -> BoardStore:
    return app.config["BOARD_STORE"]


def _ollama_client(config: AppConfig) -> OllamaClient | None:
    if not config.enable_ai:
        return None
    return OllamaClient(config.ollama_url, timeout_seconds=config.ollama_request_timeout_seconds)


def _ollama_status(config: AppConfig) -> dict[str, Any]:
    client = _ollama_client(config)
    if client is None:
        return {"available": False, "models": [], "url": config.ollama_url}
    try:
        models = client.list_models()
        return {
            "available": True,
            "models": models,
            "default_model": config.ollama_model,
            "agent_model": config.ollama_agent_model,
            "url": config.ollama_url,
        }
    except Exception:  # noqa: BLE001
        return {
            "available": False,
            "models": [],
            "default_model": config.ollama_model,
            "agent_model": config.ollama_agent_model,
            "url": config.ollama_url,
        }


def _tasks_by_status(board: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped = {status: [] for status in board["statuses"]}
    for task in board["tasks"]:
        grouped.setdefault(task["status"], []).append(task)
    return grouped


def _find_task(board: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    return next((item for item in board.get("tasks", []) if item["id"] == task_id), None)


def _task_files_dir(app: Flask, task_id: str) -> Path:
    return Path(app.config["APP_CONFIG"].data_dir) / "task_files" / task_id


def _checklist_to_text(items: list[dict[str, Any]]) -> str:
    lines = []
    for item in items:
        marker = "x" if item.get("done") else " "
        lines.append(f"- [{marker}] {item.get('text', '').strip()}")
    return "\n".join(lines)


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
    if draft_type == "rfq":
        return f"RFQ: {task['title']}"
    if draft_type == "status":
        return f"Status update: {task['title']}"
    return f"PUXAI task: {task['title']}"


def _draft_body(task: dict[str, Any], draft_type: str) -> str:
    selected_files = task.get("repo_context", {}).get("selected_files", [])[:5]
    file_list = "\n".join(f"- {path}" for path in selected_files) or "- No files linked yet"
    checklist_text = "\n".join(
        f"- {item['text']}" for item in task.get("checklist", []) if item.get("text")
    ) or "- No checklist items yet"
    if draft_type == "status":
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


def _build_rfq_markdown(task: dict[str, Any]) -> str:
    artifacts = task.get("mermaid_artifacts", {})
    attachments = task.get("attachments", [])
    files = "\n".join(f"- {item['filename']}" for item in attachments) or "- No attachments"
    checklist = "\n".join(
        f"- [{'x' if item.get('done') else ' '}] {item.get('text', '')}" for item in task.get("checklist", [])
    ) or "- No checklist items"
    return (
        f"# RFQ Brief: {task['title']}\n\n"
        f"## Summary\n{task.get('summary', '')}\n\n"
        f"## Status\n- Status: {task.get('status', '')}\n- Priority: {task.get('priority', '')}\n- Owner: {task.get('owner', '')}\n\n"
        f"## Notes\n{task.get('notes', '') or 'No notes'}\n\n"
        f"## Checklist\n{checklist}\n\n"
        f"## Attachments\n{files}\n\n"
        f"## Mermaid Flow\n```mermaid\n{artifacts.get('flow', '')}\n```\n"
    )


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
