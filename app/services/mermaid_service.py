from __future__ import annotations

import re
from typing import Any

VALID_MERMAID_PREFIXES = (
    "flowchart",
    "graph",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "stateDiagram-v2",
    "erDiagram",
    "journey",
    "gantt",
    "pie",
    "mindmap",
    "timeline",
    "gitGraph",
    "kanban",
    "quadrantChart",
    "requirementDiagram",
    "sankey-beta",
    "xychart-beta",
    "block-beta",
    "packet-beta",
    "architecture-beta",
)


def build_kanban_mermaid(board: dict[str, Any]) -> str:
    lines = ["kanban"]
    tasks_by_status: dict[str, list[dict[str, Any]]] = {status: [] for status in board.get("statuses", [])}
    for task in board.get("tasks", []):
        tasks_by_status.setdefault(task["status"], []).append(task)

    for status in board.get("statuses", []):
        lines.append(f"    {status}")
        for task in tasks_by_status.get(status, []):
            task_id = safe_id(task["id"])
            title = clean_text(task["title"])
            metadata = []
            if task.get("owner"):
                metadata.append(f"assigned: '{clean_text(task['owner'])}'")
            if task.get("priority"):
                metadata.append(f"priority: '{clean_text(task['priority'])}'")
            metadata_suffix = f"@{{ {', '.join(metadata)} }}" if metadata else ""
            lines.append(f"        {task_id}[{title}]{metadata_suffix}")
    return "\n".join(lines)


def build_stitched_board_mermaid(board: dict[str, Any]) -> str:
    lines = ["flowchart TD", '    board["PUXAI Board"]']
    for status in board.get("statuses", []):
        status_id = f"status_{safe_id(status)}"
        lines.append(f'    board --> {status_id}["{clean_text(status)}"]')
        for task in [item for item in board.get("tasks", []) if item.get("status") == status]:
            task_id = safe_id(task["id"])
            lines.append(f'    {status_id} --> {task_id}["{clean_text(task["title"])}"]')
            if task.get("repo_context", {}).get("repo_root"):
                lines.append(
                    f'    {task_id} --> {task_id}_repo["{clean_text(task["repo_context"]["repo_root"])}"]'
                )
            artifacts = task.get("mermaid_artifacts", {})
            for artifact_name in ("architecture", "flow", "kanban_subview"):
                artifact_text = str(artifacts.get(artifact_name, "")).strip()
                if artifact_text:
                    label = artifact_name.replace("_", " ")
                    lines.append(f'    {task_id} --> {task_id}_{artifact_name}["{clean_text(label)}"]')
    return "\n".join(lines)


def build_task_mermaid_artifacts(task: dict[str, Any]) -> dict[str, str]:
    repo_context = task.get("repo_context", {}) or {}
    repo_label = repo_context.get("repo_root") or repo_context.get("repo_path") or "No repo linked"
    selected_files = repo_context.get("selected_files", [])[:4]
    file_nodes = "\n".join(
        f'    repo --> {safe_id(task["id"])}_file_{index}["{clean_text(path)}"]'
        for index, path in enumerate(selected_files, start=1)
    )
    architecture = "\n".join(
        [
            "flowchart LR",
            f'    task["{clean_text(task["title"])}"] --> repo["{clean_text(repo_label)}"]',
            '    task --> agent["PUXAI Agent"]',
            '    task --> mermaid["Mermaid Artifacts"]',
            file_nodes,
        ]
    ).strip()
    if not file_nodes:
        architecture = architecture.replace("\n    repo -->", "\nrepo -->")

    flow = "\n".join(
        [
            "flowchart TD",
            f'    start["{clean_text(task["title"])}"] --> analyze["Inspect repo context"]',
            '    analyze --> plan["Propose next step"]',
            '    plan --> execute["Run safe local action"]',
            '    execute --> review["Refresh board and status"]',
        ]
    )

    kanban_subview = "\n".join(
        [
            "kanban",
            f"    {clean_text(task.get('status', 'Backlog'))}",
            f"        {safe_id(task['id'])}[{clean_text(task['title'])}]@{{ priority: '{clean_text(task.get('priority', 'Medium'))}' }}",
        ]
    )
    return {
        "architecture": architecture,
        "flow": flow,
        "kanban_subview": kanban_subview,
        "sequence": "\n".join(
            [
                "sequenceDiagram",
                "    participant User",
                "    participant PUXAI",
                "    participant Executor",
                f"    User->>PUXAI: {clean_text(task['title'])}",
                "    PUXAI->>Executor: Run safe local action",
                "    Executor-->>PUXAI: Return structured result",
                "    PUXAI-->>User: Refresh task status and artifacts",
            ]
        ),
        "mindmap": "\n".join(
            [
                "mindmap",
                f"  root(({clean_text(task['title'])}))",
                "    Repo context",
                "    Mermaid artifacts",
                "    Executor actions",
                "    Email draft",
            ]
        ),
    }


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    return cleaned or "task"


def clean_text(value: str) -> str:
    return str(value).replace("[", "(").replace("]", ")").replace('"', "'").replace("\n", " ").strip()


def validate_mermaid_text(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    warnings: list[str] = []
    first_line = ""
    diagram_type = ""

    if not text:
        warnings.append("Mermaid text is empty.")
        return {
            "ok": False,
            "warnings": warnings,
            "diagram_type": "",
            "first_line": "",
        }

    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            first_line = stripped
            break

    if not first_line:
        warnings.append("Mermaid text does not contain any diagram content.")
        return {
            "ok": False,
            "warnings": warnings,
            "diagram_type": "",
            "first_line": "",
        }

    if first_line.startswith("%%"):
        warnings.append("The first visible Mermaid line should start with a diagram type such as `flowchart TD` or `kanban`.")
    else:
        first_token = first_line.split()[0]
        diagram_type = first_token
        if first_token not in VALID_MERMAID_PREFIXES:
            warnings.append(
                "The first Mermaid line should start with a recognised diagram type such as "
                "`flowchart`, `sequenceDiagram`, `kanban`, or `mindmap`."
            )

    return {
        "ok": not warnings,
        "warnings": warnings,
        "diagram_type": diagram_type,
        "first_line": first_line,
    }


def mermaid_markdown_block(raw_text: str) -> str:
    return f"```mermaid\n{str(raw_text or '').strip()}\n```"
