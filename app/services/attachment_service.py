from __future__ import annotations

import csv
import json
from pathlib import Path
import re
from typing import Any

from app.services.board_store import utc_now


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".ini",
    ".py",
    ".html",
    ".css",
    ".yaml",
    ".yml",
}

OPTIONAL_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx"}
MAX_READ_CHARS = 60_000
MAX_PREVIEW_CHARS = 800


def summarise_attachment(path: Path) -> dict[str, Any]:
    extension = path.suffix.lower()
    size_bytes = _safe_size(path)
    summary: dict[str, Any] = {
        "filename": path.name,
        "extension": extension,
        "size_bytes": size_bytes,
        "kind": _attachment_kind(extension),
        "summary": "",
        "headings": [],
        "preview": "",
        "parsed_at": utc_now(),
    }

    if extension not in TEXT_EXTENSIONS:
        summary["summary"] = (
            "Unsupported binary or unknown file type."
            if extension not in OPTIONAL_DOCUMENT_EXTENSIONS
            else "Document parsing is not enabled for this file type yet."
        )
        return summary

    try:
        raw_text = path.read_text(encoding="utf-8", errors="ignore")[:MAX_READ_CHARS]
    except OSError as exc:
        summary["summary"] = "Attachment could not be read."
        summary["error"] = str(exc)
        return summary

    if not raw_text.strip():
        summary["summary"] = "Attachment is empty."
        return summary

    lines = raw_text.splitlines()
    summary["headings"] = _extract_headings(lines, extension)
    summary["preview"] = _build_preview(raw_text)
    summary["summary"] = _build_summary(lines, extension, raw_text, path.name)
    return summary


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _attachment_kind(extension: str) -> str:
    return {
        ".md": "markdown",
        ".txt": "text",
        ".csv": "csv",
        ".json": "json",
        ".ini": "config",
        ".py": "python",
        ".html": "html",
        ".css": "css",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".pdf": "pdf",
        ".docx": "docx",
        ".xlsx": "xlsx",
    }.get(extension, extension.lstrip(".") or "file")


def _extract_headings(lines: list[str], extension: str) -> list[str]:
    headings: list[str] = []
    if extension == ".json":
        try:
            parsed = json.loads("\n".join(lines))
            if isinstance(parsed, dict):
                headings = [str(key) for key in list(parsed.keys())[:8]]
        except json.JSONDecodeError:
            headings = []
    elif extension == ".csv":
        try:
            reader = csv.reader(lines)
            header = next(reader, [])
            headings = [item.strip() for item in header if item.strip()][:8]
        except Exception:
            headings = []
    else:
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                headings.append(line.lstrip("#").strip())
            elif re.match(r"^[A-Za-z0-9 _./-]{1,80}:$", line):
                headings.append(line[:-1].strip())
            elif extension in {".ini", ".yaml", ".yml"} and (
                (line.startswith("[") and line.endswith("]")) or re.match(r"^[A-Za-z0-9_.-]+:", line)
            ):
                headings.append(line.strip("[]"))
            if len(headings) >= 8:
                break
    return headings


def _build_preview(raw_text: str) -> str:
    preview = raw_text.strip()[:MAX_PREVIEW_CHARS]
    if len(raw_text.strip()) > MAX_PREVIEW_CHARS:
        preview = f"{preview}..."
    return preview


def _build_summary(lines: list[str], extension: str, raw_text: str, filename: str) -> str:
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    if extension == ".csv":
        try:
            reader = list(csv.reader(lines))
            row_count = max(0, len(reader) - 1)
            column_count = len(reader[0]) if reader else 0
            return f"CSV attachment with {row_count} data rows and {column_count} columns."
        except Exception:
            return "CSV attachment with readable text content."
    if extension == ".json":
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                return f"JSON attachment with {len(parsed)} top-level keys."
            if isinstance(parsed, list):
                return f"JSON attachment with a top-level list of {len(parsed)} items."
            return f"JSON attachment containing a {type(parsed).__name__} value."
        except json.JSONDecodeError:
            return "JSON-like attachment with invalid JSON syntax."
    if extension == ".py":
        function_count = len(re.findall(r"(?m)^def\s+\w+\(", raw_text))
        class_count = len(re.findall(r"(?m)^class\s+\w+", raw_text))
        return f"Python source file with {class_count} classes and {function_count} functions."
    if extension in {".yaml", ".yml", ".ini"}:
        return f"Configuration attachment with {len(non_empty_lines)} non-empty lines."
    if extension == ".md":
        heading_count = len([line for line in non_empty_lines if line.startswith("#")])
        return f"Markdown attachment with {heading_count} headings and {len(non_empty_lines)} content lines."
    if extension == ".html":
        title_match = re.search(r"<title>(.*?)</title>", raw_text, flags=re.IGNORECASE | re.DOTALL)
        if title_match:
            return f"HTML attachment titled '{title_match.group(1).strip()}'."
        return "HTML attachment with readable markup content."
    if extension == ".css":
        selector_count = raw_text.count("{")
        return f"CSS attachment with approximately {selector_count} rule blocks."
    if extension == ".txt":
        return f"Text attachment '{filename}' with {len(non_empty_lines)} non-empty lines."
    snippet = " ".join(non_empty_lines[:8])[:240]
    return snippet or f"Readable {extension.lstrip('.')} attachment."
