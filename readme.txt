PUXAI

PUXAI is now a local-first Flask workspace for Windows, macOS, and Linux.

What it does:
- Runs as a browser-based local app so the same interface works across platforms.
- Uses Ollama for local AI chat, task enrichment, and agent-style task runs.
- Keeps a kanban board with Mermaid export built into the workflow.
- Preserves local app launchers, now including macOS.

Quick start:
1. Create a virtual environment.
2. Install requirements from requirements.txt.
3. Start Ollama and pull a model such as llama3.1:8b.
4. Run python main.py
5. Open http://127.0.0.1:8787 if the browser does not auto-open.

Data is stored in:
- app/data/board.json
- app/data/session_history.json
