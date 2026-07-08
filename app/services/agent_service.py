from __future__ import annotations

import json
from typing import Any

from app.services.board_store import new_id, utc_now
from app.services.ai_backend import AIBackend
from app.services.mermaid_service import build_kanban_mermaid, build_stitched_board_mermaid


AGENT_SYSTEM_PROMPT = (
    "You are the embedded PUXAI planning agent. Be concrete, product-minded, and "
    "bias toward practical next actions. Return clean JSON only when asked."
)


def draft_task_with_ai(
    client: AIBackend,
    model: str,
    board: dict[str, Any],
    title: str,
    summary: str,
) -> dict[str, Any] | None:
    prompt = (
        "Draft a task for an agentic product board.\n"
        "Return JSON with keys: summary, priority, labels, owner, checklist, agent_brief, "
        "mermaid_artifacts, repo_context_notes.\n"
        f"Board summary: {board.get('board_summary', '')}\n"
        f"Recent notes: {json.dumps(board.get('notes', [])[:5], indent=2)}\n"
        f"Todo inbox: {json.dumps(board.get('todo_items', [])[:10], indent=2)}\n"
        f"Task title: {title}\n"
        f"Task draft: {summary}\n"
    )
    payload, _, _ = client.generate_json(model=model, prompt=prompt, system=AGENT_SYSTEM_PROMPT)
    if not payload:
        return None
    return payload


def run_task_agent(
    client: AIBackend,
    model: str,
    board: dict[str, Any],
    task: dict[str, Any],
) -> dict[str, Any] | None:
    prompt = (
        "You are running a product execution pass on one kanban task.\n"
        "Return JSON with keys: status_suggestion, summary, next_step, checklist, labels, "
        "mermaid_artifacts, notes, executor_action.\n"
        "The executor_action must be one of: repo_scan, diff_summary, generate_mermaid, document_parse, none.\n"
        "Keep checklist items short and actionable.\n"
        f"Board summary: {board.get('board_summary', '')}\n"
        f"Recent markdown notes: {json.dumps(board.get('notes', [])[:5], indent=2)}\n"
        f"Todo inbox: {json.dumps(board.get('todo_items', [])[:10], indent=2)}\n"
        f"Board mermaid:\n{build_kanban_mermaid(board)}\n"
        f"Board stitched diagram:\n{build_stitched_board_mermaid(board)}\n"
        f"Task:\n{json.dumps(task, indent=2)}\n"
    )
    payload, _, _ = client.generate_json(model=model, prompt=prompt, system=AGENT_SYSTEM_PROMPT)
    if not payload:
        return None
    return payload


def board_chat_reply(
    client: AIBackend,
    model: str,
    board: dict[str, Any],
    message: str,
) -> str:
    prompt = (
        "You are advising inside PUXAI, an agentic local-work assistant.\n"
        "Respond in concise Markdown.\n"
        f"Board summary: {board.get('board_summary', '')}\n"
        f"Recent markdown notes: {json.dumps(board.get('notes', [])[:5], indent=2)}\n"
        f"Todo inbox: {json.dumps(board.get('todo_items', [])[:10], indent=2)}\n"
        f"Board mermaid:\n{build_kanban_mermaid(board)}\n"
        f"Board stitched diagram:\n{build_stitched_board_mermaid(board)}\n"
        f"Recent ideas: {json.dumps(board.get('ideas', [])[-5:])}\n"
        f"User message: {message}\n"
    )
    return client.generate_text(model=model, prompt=prompt, system=AGENT_SYSTEM_PROMPT)


def board_chat_action_plan(
    client: AIBackend,
    model: str,
    board: dict[str, Any],
    message: str,
) -> dict[str, Any] | None:
    prompt = (
        "You are an action-taking assistant inside PUXAI.\n"
        "Return JSON only with keys: reply, actions.\n"
        "The reply should briefly summarize what you did or why you could not do it.\n"
        "The actions value must be an array of zero or more objects.\n"
        "Allowed action names are: create_note, create_todo, create_task, create_task_from_note, "
        "create_task_from_todo, create_email_draft, update_task, move_task, run_executor.\n"
        "Action arguments must use existing ids when referencing tasks, notes, or todos.\n"
        "For run_executor, executor action must be one of: repo_scan, diff_summary, generate_mermaid, document_parse.\n"
        "Do not describe steps when you can call an action directly.\n"
        "If the request is ambiguous, ask a short clarifying question in reply and return no actions.\n"
        f"Board summary: {board.get('board_summary', '')}\n"
        f"Tasks: {json.dumps(_compact_tasks(board), indent=2)}\n"
        f"Notes: {json.dumps(board.get('notes', [])[:10], indent=2)}\n"
        f"Todo inbox: {json.dumps(board.get('todo_items', [])[:20], indent=2)}\n"
        f"Recent ideas: {json.dumps(board.get('ideas', [])[-5:])}\n"
        f"User message: {message}\n"
    )
    payload, _, _ = client.generate_json(model=model, prompt=prompt, system=AGENT_SYSTEM_PROMPT)
    if not payload:
        return None
    return payload


def record_agent_run(task_id: str, kind: str, summary: str, raw: Any) -> dict[str, Any]:
    return {
        "id": new_id(),
        "task_id": task_id,
        "kind": kind,
        "summary": summary,
        "raw": raw,
        "created_at": utc_now(),
    }


def _compact_tasks(board: dict[str, Any]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for task in board.get("tasks", [])[:30]:
        compact.append(
            {
                "id": task.get("id"),
                "title": task.get("title"),
                "summary": task.get("summary"),
                "status": task.get("status"),
                "priority": task.get("priority"),
                "labels": task.get("labels", []),
            }
        )
    return compact
