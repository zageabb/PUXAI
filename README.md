# PUXAI

Personal UX and AI — a local-first AI command centre where each workspace combines tasks, notes, repositories, documents, diagrams, app launchers, and AI agents.

PUXAI is a practical local workspace built around a Flask web app, a pluggable AI backend, a kanban board, Markdown capture, Mermaid diagrams, and safe task-level actions. It is intended to feel more like an AI operating surface than a chat box with a few forms around it.

## What PUXAI Is

PUXAI is currently a local-first product workspace with:

- a browser-based Flask interface
- a kanban board for active work
- editable task workspaces
- Markdown notes and todo capture
- Mermaid diagrams attached to tasks and the board
- AI-backed chat and task agents
- repository context ingestion for grounded task work
- safe local executor actions
- cross-platform app launchers

The core idea is simple: keep context, planning, and action in one place, and let AI help with the work without pretending everything is fully autonomous yet.

## Current Features

### Flask web workspace

- Starts locally from `python main.py`
- Runs as a Flask app, by default on `http://127.0.0.1:8787/`
- Stores local board state and task context on disk

### Kanban task board

- Status-based board with default columns such as `Backlog`, `Ready`, `In Progress`, `Blocked`, `Review`, and `Done`
- Drag-and-drop and form-based task movement
- Dedicated task edit workspace for deeper task context

### Markdown notes

- Capture notes as Markdown
- Notes are visible to the AI context
- Notes can be turned into tasks

### Todo capture

- Quick lightweight inbox for smaller work items
- Todo items can later be promoted into tasks
- AI can reference todo content when drafting or planning

### Mermaid diagrams

- Task-level Mermaid artifacts such as architecture, flow, kanban subview, sequence, and mindmap
- Board-level Mermaid views for kanban and stitched board context
- Preview support in the UI

### AI chat and agents

- Board chat using the configured AI backend
- AI task enrichment during task creation
- Task agent runs that can suggest updates, checklist items, Mermaid artifacts, and next steps
- Chat action layer for supported actions like creating tasks, notes, todos, drafts, and task updates

### Repository context ingestion

- Attach a repository path to a task
- Index files and apply focus patterns
- Detect git root where available
- Pull recent commits and git status
- Generate lightweight summaries for selected files

### Safe executor actions

Current implemented executor actions:

- `repo_scan`
- `diff_summary`
- `generate_mermaid`
- `document_parse`

These actions are intentionally constrained and task-scoped.

### Cross-platform app launchers

- Shared launcher registry in `app/launchers/apps_registry.json`
- Platform-specific launch logic for Windows, macOS, and Linux
- Includes Office-oriented launcher entries such as Word, Excel, and PowerPoint

## How To Install

Requirements:

- Python 3.10 or newer
- `pip`
- An available AI backend

Optional but useful:

- Git for repository context and diff summaries
- Microsoft Office or LibreOffice for launcher workflows

macOS and Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## How To Run

From the repository root:

```bash
python main.py
```

This launches the Flask app and, if configured, opens the browser automatically.

Default local address:

- `http://127.0.0.1:8787/`

If `python` is not available in your shell path, use:

```bash
python3 main.py
```

## Configuration Using `config.ini`

PUXAI reads its runtime configuration from `config.ini`.

Important sections:

- `[general]` app name, data directory, and default workspace
- `[features]` high-level feature flags, `window_mode`, and `ai_backend`
- `[web]` host, port, debug, and browser launch behavior
- `[ollama]` Ollama URL, default model, agent model, and timeout
- `[outlook]` Outlook-related settings currently stored in config, though this is not yet a full Outlook automation surface

Current examples from the repo:

```ini
[features]
enable_ai = true
# Current backend options: ollama, dummy
# Future planned options: openai, azure_openai, copilot
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
request_timeout_seconds = 360
```

Today, `ai_backend = ollama` is the main live path. `ai_backend = dummy` can be used for testing without a running LLM. Future backend names such as `openai`, `azure_openai`, and `copilot` are reserved in the codebase but not implemented yet.

The checked-in `config.ini` may point at a LAN-hosted Ollama instance. If you are running Ollama on the same machine, update the URL accordingly.

## Ollama Setup

PUXAI currently relies on Ollama for local AI chat and agent flows.

Typical local setup:

1. Install Ollama.
2. Start the Ollama server.
3. Pull a model such as `llama3.2`.
4. Update `config.ini` if needed.

Example:

```bash
ollama pull llama3.2
ollama serve
```

Then set:

```ini
[ollama]
url = http://127.0.0.1:11434
model = llama3.2
agent_model = llama3.2
```

If the configured AI backend is offline or unreachable, the web app will still load, but AI chat and agent features will not function.

## Current Limitations

PUXAI is already useful, but there are important limits today:

- It is still a local-first single-user style workspace rather than a multi-user collaborative platform.
- Executor actions are intentionally narrow and do not provide unrestricted automation.
- Email generation currently creates task-scoped draft content inside the app; it does not send mail directly.
- Repository ingestion is lightweight and focused on selected files rather than full semantic code understanding.
- Some configuration sections exist ahead of deeper implementation, especially around Outlook and broader integrations.
- The product aims to be agentic, but not every assistant request can yet be executed as a real action.

## Suggested Roadmap

Future work, not all implemented today:

- richer approved agent actions beyond the current safe executor set
- deeper repository understanding and context-lab style ingestion
- stronger document workflows across briefs, notes, attachments, and extracted knowledge
- better task-to-agent orchestration with more reliable action planning
- more visual board interactions and richer Mermaid-linked task views
- clearer delivery surfaces for generated outputs such as drafts, artifacts, and agent results
- tighter launcher and desktop integration across Windows, macOS, and Linux

## Developer Notes

Main entry points and useful files:

- `main.py` — top-level launcher
- `app/main.py` — runtime bootstrap
- `app/web.py` — Flask routes and most application behavior
- `app/services/agent_service.py` — backend-agnostic prompts, chat planning, and task agent logic
- `app/services/ai_backend.py` — AI backend interface, factory, and backend implementations
- `app/services/executor_service.py` — safe local executor actions
- `app/services/repo_context_service.py` — repository ingestion and document summaries
- `app/services/board_store.py` — board persistence and normalization
- `app/launchers/` — cross-platform app launching

Other notes:

- State is stored locally under `app/data/`
- The board currently persists to `app/data/board.json`
- Task attachments are stored under the configured data directory
- Documentation files in the repo include `MANUAL.md` and `DESIGN_PHILOSOPHY.md`

## Honest Status

PUXAI already supports a meaningful local workflow around tasks, notes, Mermaid, repo context, and backend-driven AI assistance. It is not yet a fully autonomous agent platform, and the README should be read with that in mind. Where something sounds more ambitious than the current code, it belongs in the roadmap rather than the feature list.
