# PUXAI Design Philosophy

## Core Idea

PUXAI is intended to feel less like a chatbot inside a task app and more like a local AI workbench with a living board at its center.

The product philosophy is simple:

- work should be visible
- context should stay attached to the work
- diagrams should live with the tasks
- AI should act when safe, not only talk
- local tools should remain first-class

## 1. Local-First Over Cloud-First

PUXAI is designed to start on the user’s machine, keep state locally, and integrate with local applications and repositories.

This matters because:

- work often begins in local files, local repos, and local documents
- users need control over data and execution surfaces
- an agentic workspace is more useful when it can ground itself in the machine where the work already exists

The system should prefer:

- local storage
- local launches
- local repositories
- local document handling
- local or self-hosted model endpoints such as Ollama

## 2. The Board Is The Operating Surface

The kanban board is not just a reporting layer. It is the main control surface.

That means:

- tasks should be easy to move, inspect, and expand
- task cards should expose enough context to drive action
- board-level views should summarize the state of the system
- AI interactions should push back into the board, not live in a detached chat silo

The board should answer:

- what exists
- what matters now
- what is blocked
- what the agent thinks should happen next

## 3. Tasks Need Their Own Workspaces

A task should be more than a title and a description.

In PUXAI, a task can own:

- editable notes
- checklist state
- Mermaid artifacts
- attachments
- repo context
- email drafts
- executor history
- agent history

This is important because meaningful work rarely fits in a shallow card model. The task workspace acts as a bridge between lightweight planning and operational depth.

## 4. Mermaid Is A Native Artifact, Not Decoration

Mermaid is used because it keeps planning visual, portable, and editable as text.

PUXAI treats Mermaid as a core work artifact:

- tasks can hold multiple Mermaid views
- the board can generate board-level Mermaid
- visual planning stays versionable and legible

This supports a style of working where:

- diagrams evolve with execution
- architecture stays attached to delivery
- planning visuals are easy for AI to read and regenerate

## 5. Agentic, But Bounded

PUXAI is meant to be agentic, but not reckless.

There is a deliberate distinction between:

- advice
- approved in-app actions
- approved local executor actions
- unrestricted automation

The current product intentionally stops before unrestricted automation.

That boundary exists to preserve:

- predictability
- trust
- auditability
- safe iteration

An agent should be able to do useful work, but the user should still understand the execution surface and the risk profile.

## 6. Context Before Action

AI quality improves when the system is grounded in the actual work.

That is why PUXAI pulls context from:

- the board summary
- recent notes
- todo items
- task detail
- repository context
- parsed documents
- Mermaid artifacts

The philosophy is that action quality depends on context quality. A weakly grounded agent becomes a suggestion engine. A context-rich agent becomes materially useful.

## 7. Capture Should Be Lightweight

Not every idea deserves a task immediately.

PUXAI includes markdown notes and todo capture because:

- some ideas begin as fragments
- research often arrives before structure
- the board should not become cluttered with premature tasks

Capture first, then promote when ready.

This keeps the board cleaner while still allowing AI to mine the raw material later.

## 8. Human Editing Must Stay Easy

Agentic systems fail when users lose the ability to directly shape the work.

That is why PUXAI keeps explicit editing front and center:

- task fields are editable
- Mermaid is editable
- notes are editable
- repo context is refreshable
- generated outputs can be reviewed

Users should be able to steer, refine, and correct the system without fighting abstraction.

## 9. Cross-Platform Practicality Matters

PUXAI is meant to work across Windows, macOS, and Linux because real work environments are mixed.

Cross-platform support is not only a compatibility feature. It reflects a broader principle:

- agentic tools should meet users where they already work

That includes:

- browser-based UI
- per-platform launchers
- flexible local configuration
- graceful fallback behavior

## 10. The Product Should Grow Toward A Real Work Console

The long-term direction is not a prettier note-taking app. It is a real operating console for human-plus-agent work.

That implies future growth in areas like:

- richer approved agents
- stronger repo-aware execution
- more document-aware workflows
- better multi-artifact task context
- board actions that trigger real, safe work

The test for new features should be:

- does this make the workspace more actionable
- does this keep context attached to execution
- does this preserve trust
- does this make AI materially useful, not merely present

## Closing Principle

PUXAI should help a person move from idea, to structure, to action, to evidence, to completion without leaving the workspace or losing context.

