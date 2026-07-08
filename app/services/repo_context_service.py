from __future__ import annotations

from fnmatch import fnmatch
import json
from pathlib import Path
import subprocess
from typing import Any

from app.services.board_store import utc_now


TEXT_EXTENSIONS = {".md", ".txt", ".py", ".js", ".ts", ".tsx", ".json", ".yaml", ".yml", ".ini", ".html", ".css"}
IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
}
IMPORTANT_NAME_HINTS = (
    "readme",
    "pyproject",
    "requirements",
    "package",
    "config",
    "app",
    "main",
    "router",
    "service",
    "model",
)
PREFERRED_EXTENSIONS = {".py", ".md", ".json", ".yaml", ".yml", ".ini"}
DEPENDENCY_FILENAMES = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.py",
    "setup.cfg",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}


def ingest_repository_context(repo_path: str, focus_patterns: str, notes: str = "") -> dict[str, Any]:
    resolved = resolve_repo_path(repo_path)
    patterns = [pattern.strip() for pattern in focus_patterns.split(",") if pattern.strip()] or ["*.py", "*.md", "*.json"]
    all_files = list_repository_files(resolved)
    scored_files = score_repository_files(resolved, all_files, patterns)
    selected_files = [item["path"] for item in scored_files[:12]]
    if not selected_files:
        selected_files = all_files[:12]

    documents = [read_document_summary(resolved / relative_path) for relative_path in selected_files[:6]]
    git_root = get_git_root(resolved)
    detected_languages = detect_languages(all_files)
    detected_frameworks = detect_frameworks(resolved, all_files)
    important_files = detect_important_files(all_files)
    dependency_files = [path for path in all_files if Path(path).name.lower() in DEPENDENCY_FILENAMES][:12]
    folder_summary = summarize_folders(all_files)
    last_scan_stats = {
        "total_files": len(all_files),
        "matched_files": sum(1 for path in all_files if any(fnmatch(path, pattern) for pattern in patterns)),
        "selected_files": len(selected_files),
        "documents_read": len(documents),
    }
    summary_lines = [
        f"Repo path: {resolved}",
        f"Files indexed: {len(all_files)}",
        f"Focus patterns: {', '.join(patterns)}",
    ]
    if detected_frameworks:
        summary_lines.append(f"Frameworks: {', '.join(detected_frameworks)}")
    if important_files:
        summary_lines.append(f"Important files: {', '.join(important_files[:6])}")
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
        "detected_languages": detected_languages,
        "detected_frameworks": detected_frameworks,
        "important_files": important_files,
        "folder_summary": folder_summary,
        "dependency_files": dependency_files,
        "last_scan_stats": last_scan_stats,
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
        files = [
            Path(line).relative_to(repo_root).as_posix()
            for line in result.stdout.splitlines()
            if line.strip()
        ]
        files = [path for path in files if not is_ignored_relative_path(path)]
        if files:
            return files
    except Exception:
        pass

    files: list[str] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        files.append(path.relative_to(repo_root).as_posix())
        if len(files) >= 250:
            break
    return files


def is_ignored_relative_path(relative_path: str) -> bool:
    path = Path(relative_path)
    return any(part in IGNORED_DIRS for part in path.parts)


def score_repository_files(
    repo_root: Path,
    all_files: list[str],
    patterns: list[str],
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for relative_path in all_files:
        path = repo_root / relative_path
        if not path.is_file() or is_ignored_relative_path(relative_path):
            continue
        score = 0.0
        filename = path.name.lower()
        extension = path.suffix.lower()
        depth = len(Path(relative_path).parts)
        if any(fnmatch(relative_path, pattern) for pattern in patterns):
            score += 12
        if any(hint in filename for hint in IMPORTANT_NAME_HINTS):
            score += 18
        if extension in PREFERRED_EXTENSIONS:
            score += 10
        if depth <= 2:
            score += 8
        elif depth <= 4:
            score += 4
        try:
            size_bytes = path.stat().st_size
        except OSError:
            size_bytes = 0
        if size_bytes and size_bytes < 50_000:
            score += 6
        elif size_bytes < 250_000:
            score += 3
        else:
            score -= 4
        scored.append({"path": relative_path, "score": score, "size_bytes": size_bytes})
    scored.sort(key=lambda item: (-item["score"], item["path"]))
    return scored


def detect_languages(all_files: list[str]) -> list[str]:
    languages: set[str] = set()
    for relative_path in all_files:
        suffix = Path(relative_path).suffix.lower()
        if suffix == ".py":
            languages.add("Python")
        elif suffix in {".js", ".jsx"}:
            languages.add("JavaScript")
        elif suffix in {".ts", ".tsx"}:
            languages.add("TypeScript")
        elif suffix in {".md"}:
            languages.add("Markdown")
        elif suffix in {".json"}:
            languages.add("JSON")
        elif suffix in {".yaml", ".yml"}:
            languages.add("YAML")
        elif suffix in {".ini"}:
            languages.add("INI")
        elif suffix in {".html", ".css"}:
            languages.add("Web")
    return sorted(languages)


def detect_frameworks(repo_root: Path, all_files: list[str]) -> list[str]:
    frameworks: set[str] = set()
    file_set = set(all_files)
    sample_text = build_detection_text(repo_root, all_files)

    if "app.py" in file_set or "web.py" in file_set or "templates/" in sample_text or "static/" in sample_text:
        if "from flask" in sample_text or "import flask" in sample_text or "flask" in sample_text:
            frameworks.add("Flask")
    if "from fastapi" in sample_text or "import fastapi" in sample_text:
        frameworks.add("FastAPI")
    if "manage.py" in file_set or any(path.endswith("settings.py") for path in all_files):
        frameworks.add("Django")
    if "rxconfig.py" in file_set or "import reflex" in sample_text or "from reflex" in sample_text:
        frameworks.add("Reflex")
    if "package.json" in file_set:
        frameworks.add("Node")
    if any(name in file_set for name in ("pyproject.toml", "requirements.txt", "setup.py")):
        frameworks.add("Python")
    return sorted(frameworks)


def build_detection_text(repo_root: Path, all_files: list[str]) -> str:
    interesting = [
        path for path in all_files
        if Path(path).name.lower() in {"app.py", "web.py", "main.py", "manage.py", "rxconfig.py", "package.json", "requirements.txt", "pyproject.toml"}
    ][:10]
    chunks = []
    for relative_path in interesting:
        try:
            raw = (repo_root / relative_path).read_text(encoding="utf-8", errors="ignore")[:5000]
        except OSError:
            continue
        chunks.append(raw.lower())
    chunks.extend(path.lower() for path in all_files[:50])
    return "\n".join(chunks)


def detect_important_files(all_files: list[str]) -> list[str]:
    important = []
    for relative_path in all_files:
        filename = Path(relative_path).name.lower()
        if filename in DEPENDENCY_FILENAMES or any(hint in filename for hint in IMPORTANT_NAME_HINTS):
            important.append(relative_path)
    return important[:12]


def summarize_folders(all_files: list[str]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for relative_path in all_files:
        parts = Path(relative_path).parts
        top_level = parts[0] if len(parts) > 1 else "root"
        counts[top_level] = counts.get(top_level, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [
        {"folder": folder, "file_count": file_count}
        for folder, file_count in ranked[:10]
    ]


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
