# PUXAI Manual

## Purpose

PUXAI is a local-first workspace for planning, capturing, visualizing, and executing work with AI assistance. It is designed to keep the board, the task details, the diagrams, and the local machine in one loop.

## Starting PUXAI

From the repository root:

```bash
python main.py
```

Expected result:

- Flask starts on the host and port defined in [`config.ini`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/config.ini)
- By default this is `http://127.0.0.1:8787/`
- Your browser opens automatically if `auto_open_browser = true`

If the browser opens but AI is unavailable, check the Ollama URL and model settings.

## The Main Screen

The home screen is organized into four major areas:

### Hero Header

Shows:

- board title
- board summary
- counts for tasks, agent runs, and available models
- a `New task` button
- a `Refresh Mermaid Views` button
- a toggle for hiding or showing the AI side rail

### Live Kanban Surface

This is the central operating surface.

Each column maps to a task status:

- `Backlog`
- `Ready`
- `In Progress`
- `Blocked`
- `Review`
- `Done`

Each card can show:

- title
- summary
- owner
- updated date
- labels
- checklist
- latest agent brief
- recent agent notes
- recent executor notes

Available card actions:

- `Run agent`
- `Edit`
- manual status change
- drag between columns

Expanding `Task context and artifacts` reveals:

- repository summary
- linked files
- parsed documents
- Mermaid previews
- recent executor activity

### Board Mermaid

This section shows two board-level visualizations:

- `Board kanban`
- `Stitched board`

Click either preview to open a larger rendered view.

### Capture And AI Rail

The lower and right-side areas support:

- markdown note capture
- todo capture
- task conversion from notes or todos
- AI chat and action-taking

## Creating A Task

Use the `New task` button instead of the older inline task block.

Fields:

- `Title`
- `Summary`
- `Status`
- `Priority`
- `Owner`
- `Labels`
- `Use Ollama to enrich this task`

When enrichment is enabled, PUXAI may draft:

- better task summary wording
- checklist items
- labels
- task owner suggestion
- an agent brief
- Mermaid artifact seeds

## Editing A Task Workspace

Open a task with the `Edit` button.

The task workspace is the main detailed editing surface.

### Core Task Details

You can edit:

- title
- owner
- status
- priority
- labels
- summary
- agent brief
- notes
- checklist

### Mermaid Artifacts

Each task can hold multiple Mermaid artifacts:

- architecture
- flow
- kanban subview
- sequence
- mindmap

These are editable in the task workspace and previewed below the editor.

### File Handling

Each task can store:

- attachments uploaded through the task workspace
- repository context from a local folder

Repo context fields:

- `Repository path`
- `Focus patterns`
- `Repo notes`

Selecting `Refresh repo context` updates:

- repo summary
- file index
- selected files
- git status
- recent commits
- lightweight document summaries

### Email Actions

Current email draft options:

- `Work Brief`
- `Status update`

The app generates a stored draft record inside the task workspace. It does not send the email automatically.

### Executor

The executor performs safe local actions.

Available actions today:

- `repo_scan`
- `diff_summary`
- `generate_mermaid`
- `document_parse`

Use these when you want the system to work with local context in a controlled way.

### Execution Trace

Recent executor runs are recorded on the task so you can see what happened and when.

### Delete Task

The `Delete task` button removes:

- the task
- associated task-scoped attachments

Use with care.

## Notes And Todo Capture

### Markdown Notes

Notes are first-class input.

Use them for:

- research
- call notes
- meeting capture
- loose ideas
- draft prompts
- working decisions

Notes are stored as markdown and rendered back in the UI.

### Todo Items

Todo items are lighter-weight capture entries.

Use them for:

- quick actions
- reminders
- items not ready to become full tasks yet

### Turning Capture Into Tasks

Notes and todo items can be promoted into tasks.

This is useful when:

- a rough idea becomes execution work
- research needs a tracked delivery item
- the AI identifies a todo that should become board work

## AI Chat And Actions

The board chat does two kinds of work:

### Advisory Mode

If the request is broad, uncertain, or outside the approved action set, the assistant responds in markdown and suggests what to do.

### Action Mode

If the request is clear and supported, the assistant can execute actions directly.

Current supported chat actions:

- create note
- create todo
- create task
- create task from note
- create task from todo
- create email draft
- update task
- move task
- run executor

This means prompts like these can work:

- "Create a task for improving the launcher reliability"
- "Turn my latest note into a task"
- "Move the Office launcher task to Review"
- "Create a status update draft for the tender workflow task"
- "Run a repo scan on the task linked to this repo"

## Board Mermaid Explained

### Board Kanban

This is a Mermaid representation of the board grouped by status. It gives you a fast visual snapshot of work distribution.

Use it when you want to:

- review board structure at a glance
- discuss flow in a more diagrammatic format
- export or reuse the board structure in Mermaid-aware tools

### Stitched Board

This is a broader Mermaid diagram that connects work items as a system instead of only as lanes.

Use it when you want to:

- explain how tasks relate
- describe a broader operating flow
- see board work as connected delivery logic

## Local Launchers

PUXAI can trigger local applications through platform-specific launchers.

Current launcher architecture:

- shared registry in [`app/launchers/apps_registry.json`](/Users/geraldabbot/Documents/Codex/2026-07-06/li/PUXAI/app/launchers/apps_registry.json)
- Windows launcher
- macOS launcher
- Linux launcher

Office apps such as Word, Excel, and PowerPoint are handled through this registry.

## Configuration Tips

If AI is not working:

- verify Ollama is running
- verify the configured model exists
- verify `config.ini` points to the right Ollama URL

If the app opens the wrong mode:

- ensure `window_mode = web`

If the server is not visible:

- confirm you launched with `python main.py` from the repo root
- confirm the configured host and port are not already in use

If repo actions fail:

- verify the repository path exists
- verify Git is installed if you expect git summaries

## Suggested Usage Pattern

1. Capture ideas into notes or todos quickly.
2. Promote the right items into tasks.
3. Enrich tasks with AI.
4. Link repo context and attachments.
5. Generate Mermaid views as the task evolves.
6. Use the agent for next steps and status movement.
7. Use executor actions when you want grounded local context.
8. Keep the board as the single visible truth of work.

