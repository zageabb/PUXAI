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
from app.services.board_store import BoardStore, new_id, utc_now
from app.services.mermaid_service import build_kanban_mermaid
from app.services.ollama_client import OllamaClient

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
            "board_preview_mermaid": board.get("board_mermaid") or build_kanban_mermaid(board),
        }

    @app.get("/")
    def index() -> str:
        board = _board_store(app).load()
        if not board.get("board_mermaid"):
            board["board_mermaid"] = build_kanban_mermaid(board)
            _board_store(app).save(board)
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
            "mermaid_code": "",
            "latest_agent_notes": "",
            "created_at": utc_now(),
            "updated_at": utc_now(),
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
                    task["mermaid_code"] = ai_payload.get("mermaid_code", "")

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
        _board_store(app).update_task(task_id, {"status": status})
        _refresh_mermaid(app)
        return redirect(url_for("index"))

    @app.post("/tasks/<task_id>/agent")
    def task_agent(task_id: str) -> Any:
        board = _board_store(app).load()
        task = next((item for item in board["tasks"] if item["id"] == task_id), None)
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
        merged_labels = sorted({*task.get("labels", []), *[str(label).strip() for label in payload.get("labels", []) if str(label).strip()]})
        notes = payload.get("notes", "")
        _board_store(app).update_task(
            task_id,
            {
                "status": suggested_status,
                "summary": payload.get("summary", task["summary"]),
                "checklist": checklist,
                "labels": merged_labels,
                "mermaid_code": payload.get("mermaid_code", task.get("mermaid_code", "")),
                "latest_agent_notes": notes,
                "agent_brief": payload.get("next_step", task.get("agent_brief", "")),
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
        task = next((item for item in board["tasks"] if item["id"] == task_id), None)
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
        flash("Board Mermaid view refreshed.", "success")
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


def _refresh_mermaid(app: Flask) -> None:
    board = _board_store(app).load()
    board["board_mermaid"] = build_kanban_mermaid(board)
    _board_store(app).save(board)
