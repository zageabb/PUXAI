from __future__ import annotations

from fnmatch import fnmatch
import json
from pathlib import Path
import subprocess
from typing import Any

from app.services.board_store import utc_now


TEXT_EXTENSIONS = {".md", ".txt", ".py", ".js", ".ts", ".tsx", ".json", ".yaml", ".yml", ".ini", ".html", ".css"}


def ingest_repository_context(repo_path: str, focus_patterns: str, notes: str = "") -> dict[str, Any]:
    resolved = resolve_repo_path(repo_path)
    patterns = [pattern.strip() for pattern in focus_patterns.split(",") if pattern.strip()] or ["*.py", "*.md", "*.json"]
    all_files = list_repository_files(resolved)
    selected_files = [path for path in all_files if any(fnmatch(path, pattern) for pattern in patterns)][:12]
    if not selected_files:
        selected_files = all_files[:12]

    documents = [read_document_summary(resolved / relative_path) for relative_path in selected_files[:6]]
    git_root = get_git_root(resolved)
    summary_lines = [
        f"Repo path: {resolved}",
        f"Files indexed: {len(all_files)}",
        f"Focus patterns: {', '.join(patterns)}",
    ]
    if git_root:
        summary_lines.append(f"Git root: {git_root}")
    if notes.strip():
        summary_lines.append(f"Notes: {notes.strip()}")

    return {
        "repo_path": str(resolved),
        "focus_patterns": ", ".join(patterns),
        "notes": notes.strip(),
        "repo_root": str(git_root or resolved),
        "is_git_repo": bool(git_root),
        "sample_files": all_files[:24],
        "selected_files": selected_files,
        "git_status": git_status_lines(git_root or resolved),
        "recent_commits": recent_commit_lines(git_root or resolved),
        "documents": documents,
        "summary": "\n".join(summary_lines),
        "last_ingested_at": utc_now(),
    }


def resolve_repo_path(repo_path: str) -> Path:
    candidate = Path(repo_path or ".").expanduser()
    resolved = candidate.resolve()
    if not resolved.exists():
        raise ValueError(f"Repository path does not exist: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"Repository path is not a directory: {resolved}")
    return resolved


def list_repository_files(repo_root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["rg", "--files", str(repo_root)],
            check=True,
            capture_output=True,
            text=True,
        )
        files = [Path(line).relative_to(repo_root).as_posix() for line in result.stdout.splitlines() if line.strip()]
        if files:
            return files
    except Exception:
        pass

    files: list[str] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".git") or part == "__pycache__" for part in path.parts):
            continue
        files.append(path.relative_to(repo_root).as_posix())
        if len(files) >= 250:
            break
    return files


def get_git_root(path: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    output = result.stdout.strip()
    return Path(output) if output else None


def git_status_lines(path: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()][:20]


def recent_commit_lines(path: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "log", "--oneline", "-n", "8"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def read_document_summary(path: Path) -> dict[str, Any]:
    extension = path.suffix.lower()
    if extension not in TEXT_EXTENSIONS:
        return {
            "path": str(path),
            "kind": extension.lstrip(".") or "file",
            "summary": "Binary or unsupported text file for quick parsing.",
            "headings": [],
        }
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return {
            "path": str(path),
            "kind": extension.lstrip(".") or "file",
            "summary": f"Could not read file: {exc}",
            "headings": [],
        }
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    headings = [line for line in lines if line.startswith("#") or line.endswith(":")][:6]
    summary = " ".join(lines[:10])[:500]
    return {
        "path": str(path),
        "kind": extension.lstrip(".") or "file",
        "summary": summary,
        "headings": headings,
    }


def json_preview(data: Any) -> str:
    return json.dumps(data, indent=2)[:1200]
