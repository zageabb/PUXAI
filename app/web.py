"""Flask application for the PUXAI local workspace."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

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
            return redirect(url_for("index"))

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
        return redirect(url_for("index"))

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
        return redirect(url_for("index"))

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
        return redirect(url_for("index"))

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
