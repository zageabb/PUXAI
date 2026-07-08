# PUXAI

PUXAI is a local-first, agentic workspace for turning work into visible, editable, executable tasks.

It combines a Flask web app, an Ollama-backed assistant, a live kanban board, Mermaid-based visual planning, local app launching, task-scoped repository context, markdown notes, todo capture, and safe local executor actions.

## What PUXAI Does

- Runs as a local web app by default at `http://127.0.0.1:8787/`
- Uses Ollama for task drafting, task-agent runs, and board chat
- Organizes work on a kanban board with editable task workspaces
- Stores Mermaid artifacts per task and at board level
- Captures markdown notes and todo items that AI can see and convert into tasks
- Lets tasks carry attachments, repo context, document summaries, and email drafts
- Launches local apps on Windows, macOS, and Linux through a shared launcher registry
- Supports safe executor actions such as repo scans, diff summaries, Mermaid regeneration, and lightweight document parsing

## Current Shape Of The Product

PUXAI is not a generic chatbot wrapped in a dashboard. It is closer to a local AI operating surface:

- The board is the primary planning layer
- Each task has its own workspace
- AI can both advise and perform approved in-app actions
- Mermaid is treated as part of the work, not as an afterthought
- Local tools and local data remain first-class

## Requirements

- Python 3.10+
- `pip`
- Ollama running locally or on a reachable LAN host
- A pulled model for chat and agent runs

Optional:

- Microsoft Office or LibreOffice for launcher workflows
- Git for repo context and diff summaries

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

PUXAI reads from [`config.ini`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/config.ini).

Important settings:

- `window_mode = web` keeps the app in Flask/web mode
- `[web] host` and `port` control the local server address
- `[ollama] url` points to your Ollama server
- `[ollama] model` is the default assistant model
- `[ollama] agent_model` is used for structured agent runs
- `auto_open_browser = true` opens the browser shortly after launch

Example launch-focused configuration:

```ini
[features]
enable_ai = true
ai_backend = ollama
window_mode = web

[web]
host = 127.0.0.1
port = 8787
auto_open_browser = true

[ollama]
url = http://127.0.0.1:11434
model = llama3.2
agent_model = llama3.2
```

## Running The App

Start the application from the repository root:

```bash
python main.py
```

If everything is configured correctly, PUXAI starts a Flask server and opens:

- `http://127.0.0.1:8787/`

## Main Workflows

### 1. Create Work

- Click `New task`
- Enter title, summary, status, owner, labels, and priority
- Leave AI enrichment on if you want Ollama to draft checklist items, task hints, and Mermaid seeds

### 2. Edit A Task Workspace

Each task has a dedicated workspace where you can:

- edit title, summary, notes, labels, owner, priority, and status
- manage checklist items
- author Mermaid artifacts such as architecture, flow, kanban subview, sequence, and mindmap
- attach files
- ingest repository context
- generate email drafts
- run safe executor actions
- delete the task
- download a task `Work Brief`

### 3. Use Capture As Input

- Save markdown notes
- Add todo items
- Convert either into tasks
- Let the AI use that captured material as context

### 4. Use The Assistant As An Action Layer

The board chat can currently take direct action for supported requests, including:

- create note
- create todo
- create task
- create task from note
- create task from todo
- create email draft
- update task
- move task
- run executor action

If a request falls outside the approved action layer, the assistant will respond conversationally instead of executing.

## Safe Executor Actions

Current executor actions:

- `repo_scan`
- `diff_summary`
- `generate_mermaid`
- `document_parse`

These are intentionally constrained. They are meant to make the system more agentic without turning it into an unrestricted local automation shell.

## Repository Context

Tasks can ingest repo context from a local path. PUXAI will:

- resolve the directory
- index files
- filter by focus patterns
- detect git root when available
- collect git status and recent commits
- generate lightweight summaries for selected text-like files

This gives the agent more grounded context before acting.

## Local App Launching

PUXAI includes a cross-platform launcher registry in [`app/launchers/apps_registry.json`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/app/launchers/apps_registry.json).

Current launcher support includes platform-aware commands for apps such as:

- Microsoft Word
- Microsoft Excel
- Microsoft PowerPoint
- Outlook and other Office-adjacent entries

Launch behavior is implemented per platform in:

- [`app/launchers/windows_launcher.py`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/app/launchers/windows_launcher.py)
- [`app/launchers/macos_launcher.py`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/app/launchers/macos_launcher.py)
- [`app/launchers/linux_launcher.py`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/app/launchers/linux_launcher.py)

## Data Storage

Board state is stored locally under the configured data directory, by default:

- `app/data/board.json`

Task attachments are stored under the app data area as task-scoped files.

## Key Files

- [`main.py`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/main.py): top-level launcher
- [`app/main.py`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/app/main.py): runtime entry logic
- [`app/web.py`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/app/web.py): Flask routes and application behavior
- [`app/services/agent_service.py`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/app/services/agent_service.py): AI drafting, chat, and action planning
- [`app/services/executor_service.py`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/app/services/executor_service.py): safe local executor actions
- [`app/services/repo_context_service.py`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/app/services/repo_context_service.py): repository ingestion
- [`app/services/board_store.py`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/app/services/board_store.py): local board persistence

## Documentation

- [`MANUAL.md`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/MANUAL.md)
- [`DESIGN_PHILOSOPHY.md`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/DESIGN_PHILOSOPHY.md)

## Near-Term Direction

Strong next moves for PUXAI include:

- richer agent execution with more approved local actions
- tighter repo-aware task grounding before agent runs
- multi-artifact Mermaid views per task
- board interactions that behave more like a live operating console than a CRUD dashboard

