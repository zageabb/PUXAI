from __future__ import annotations

import json
from typing import Any

from app.services.board_store import new_id, utc_now
from app.services.mermaid_service import build_kanban_mermaid
from app.services.ollama_client import OllamaClient


AGENT_SYSTEM_PROMPT = (
    "You are the embedded PUXAI planning agent. Be concrete, product-minded, and "
    "bias toward practical next actions. Return clean JSON only when asked."
)


def draft_task_with_ai(
    client: OllamaClient,
    model: str,
    board: dict[str, Any],
    title: str,
    summary: str,
) -> dict[str, Any] | None:
    prompt = (
        "Draft a task for an agentic product board.\n"
        "Return JSON with keys: summary, priority, labels, owner, checklist, agent_brief, mermaid_code.\n"
        f"Board summary: {board.get('board_summary', '')}\n"
        f"Task title: {title}\n"
        f"Task draft: {summary}\n"
    )
    payload, _, _ = client.generate_json(model=model, prompt=prompt, system=AGENT_SYSTEM_PROMPT)
    if not payload:
        return None
    return payload


def run_task_agent(
    client: OllamaClient,
    model: str,
    board: dict[str, Any],
    task: dict[str, Any],
) -> dict[str, Any] | None:
    prompt = (
        "You are running a product execution pass on one kanban task.\n"
        "Return JSON with keys: status_suggestion, summary, next_step, checklist, labels, mermaid_code, notes.\n"
        "Keep checklist items short and actionable.\n"
        f"Board summary: {board.get('board_summary', '')}\n"
        f"Board mermaid:\n{build_kanban_mermaid(board)}\n"
        f"Task:\n{json.dumps(task, indent=2)}\n"
    )
    payload, _, _ = client.generate_json(model=model, prompt=prompt, system=AGENT_SYSTEM_PROMPT)
    if not payload:
        return None
    return payload


def board_chat_reply(
    client: OllamaClient,
    model: str,
    board: dict[str, Any],
    message: str,
) -> str:
    prompt = (
        "You are advising inside PUXAI, an agentic local-work assistant.\n"
        "Respond in concise Markdown.\n"
        f"Board summary: {board.get('board_summary', '')}\n"
        f"Board mermaid:\n{build_kanban_mermaid(board)}\n"
        f"Recent ideas: {json.dumps(board.get('ideas', [])[-5:])}\n"
        f"User message: {message}\n"
    )
    return client.generate_text(model=model, prompt=prompt, system=AGENT_SYSTEM_PROMPT)


def record_agent_run(task_id: str, kind: str, summary: str, raw: Any) -> dict[str, Any]:
    return {
        "id": new_id(),
        "task_id": task_id,
        "kind": kind,
        "summary": summary,
        "raw": raw,
        "created_at": utc_now(),
    }
