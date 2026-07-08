from __future__ import annotations

import csv
import json
from pathlib import Path
import re
from typing import Any
import zipfile
from xml.etree import ElementTree as ET

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
OFFICE_EXTENSIONS = {
    ".docx",
    ".docm",
    ".xlsx",
    ".xlsm",
    ".pptx",
    ".pptm",
}
ODF_EXTENSIONS = {
    ".odt",
    ".ods",
    ".odp",
    ".odg",
}
OPTIONAL_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".xls", ".ppt"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | OFFICE_EXTENSIONS | ODF_EXTENSIONS

MAX_READ_CHARS = 60_000
MAX_PREVIEW_CHARS = 800
MAX_HEADING_COUNT = 8
MAX_TEXT_PARTS = 400


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

    try:
        parsed = parse_attachment_content(path)
    except OSError as exc:
        summary["summary"] = "Attachment could not be read."
        summary["error"] = str(exc)
        return summary

    if parsed.get("error"):
        summary["summary"] = parsed.get("summary", "Attachment could not be parsed.")
        summary["headings"] = parsed.get("headings", [])
        summary["preview"] = parsed.get("preview", "")
        summary["error"] = parsed["error"]
        return summary

    summary["summary"] = parsed.get("summary", "")
    summary["headings"] = parsed.get("headings", [])
    summary["preview"] = parsed.get("preview", "")
    return summary


def parse_attachment_content(path: Path) -> dict[str, Any]:
    extension = path.suffix.lower()
    if extension in TEXT_EXTENSIONS:
        return _parse_text_attachment(path, extension)
    if extension in OFFICE_EXTENSIONS:
        return _parse_office_attachment(path, extension)
    if extension in ODF_EXTENSIONS:
        return _parse_odf_attachment(path, extension)
    if extension in OPTIONAL_DOCUMENT_EXTENSIONS:
        return {
            "summary": "Document parsing is not enabled for this file type yet.",
            "headings": [],
            "preview": "",
        }
    return {
        "summary": "Unsupported binary or unknown file type.",
        "headings": [],
        "preview": "",
    }


def _parse_text_attachment(path: Path, extension: str) -> dict[str, Any]:
    raw_text = path.read_text(encoding="utf-8", errors="ignore")[:MAX_READ_CHARS]
    if not raw_text.strip():
        return {
            "summary": "Attachment is empty.",
            "headings": [],
            "preview": "",
        }

    lines = raw_text.splitlines()
    return {
        "summary": _build_summary(lines, extension, raw_text, path.name),
        "headings": _extract_headings(lines, extension),
        "preview": _build_preview(raw_text),
    }


def _parse_office_attachment(path: Path, extension: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            if extension in {".docx", ".docm"}:
                text_parts = _office_document_parts(archive, "word/document.xml")
                headings = _docx_headings(archive, text_parts)
                summary = f"Word document with approximately {len(text_parts)} text blocks."
            elif extension in {".xlsx", ".xlsm"}:
                text_parts, headings = _xlsx_text_and_headings(archive)
                summary = f"Spreadsheet workbook with {len(headings) or 1} sheet name(s)."
            else:
                text_parts, headings = _pptx_text_and_headings(archive)
                summary = f"Presentation with approximately {len(headings) or 1} slide heading(s)."
    except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        return {
            "summary": "Office document could not be parsed.",
            "headings": [],
            "preview": "",
            "error": str(exc),
        }

    text = "\n".join(text_parts).strip()
    if not text:
        return {
            "summary": "Office document did not contain extractable text.",
            "headings": headings[:MAX_HEADING_COUNT],
            "preview": "",
        }
    return {
        "summary": summary,
        "headings": headings[:MAX_HEADING_COUNT],
        "preview": _build_preview(text),
    }


def _parse_odf_attachment(path: Path, extension: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            content = archive.read("content.xml")
            root = ET.fromstring(content)
            text_parts = _xml_text_parts(root)
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        return {
            "summary": "OpenDocument file could not be parsed.",
            "headings": [],
            "preview": "",
            "error": str(exc),
        }

    text = "\n".join(text_parts).strip()
    headings = [part for part in text_parts if len(part.split()) <= 10][:MAX_HEADING_COUNT]
    kind_label = {
        ".odt": "LibreOffice Writer document",
        ".ods": "LibreOffice Calc workbook",
        ".odp": "LibreOffice Impress presentation",
        ".odg": "LibreOffice Draw document",
    }.get(extension, "OpenDocument file")
    if not text:
        return {
            "summary": f"{kind_label} did not contain extractable text.",
            "headings": headings,
            "preview": "",
        }
    return {
        "summary": f"{kind_label} with extractable text content.",
        "headings": headings,
        "preview": _build_preview(text),
    }


def _office_document_parts(archive: zipfile.ZipFile, member_name: str) -> list[str]:
    content = archive.read(member_name)
    root = ET.fromstring(content)
    return _xml_text_parts(root)


def _docx_headings(archive: zipfile.ZipFile, text_parts: list[str]) -> list[str]:
    try:
        styles_xml = archive.read("word/styles.xml")
        styles_root = ET.fromstring(styles_xml)
        heading_style_ids = {
            style.attrib.get(_qn("w:styleId"), "")
            for style in styles_root.findall(f".//{_qn('w:style')}")
            if "heading" in (style.attrib.get(_qn("w:styleId"), "")).lower()
        }
    except (KeyError, ET.ParseError):
        heading_style_ids = set()

    try:
        content = archive.read("word/document.xml")
        root = ET.fromstring(content)
    except (KeyError, ET.ParseError):
        return text_parts[:MAX_HEADING_COUNT]

    headings: list[str] = []
    for paragraph in root.findall(f".//{_qn('w:p')}"):
        text = "".join(node.text or "" for node in paragraph.findall(f".//{_qn('w:t')}")).strip()
        if not text:
            continue
        style_node = paragraph.find(f".//{_qn('w:pStyle')}")
        style_id = style_node.attrib.get(_qn("w:val"), "") if style_node is not None else ""
        if style_id in heading_style_ids or style_id.lower().startswith("heading"):
            headings.append(text)
        if len(headings) >= MAX_HEADING_COUNT:
            break
    return headings or text_parts[:MAX_HEADING_COUNT]


def _xlsx_text_and_headings(archive: zipfile.ZipFile) -> tuple[list[str], list[str]]:
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    sheet_names = [
        sheet.attrib.get("name", "").strip()
        for sheet in workbook_root.findall(f".//{_qn('x:sheet')}")
        if sheet.attrib.get("name", "").strip()
    ]
    shared_strings = _xlsx_shared_strings(archive)
    text_parts: list[str] = []
    for member_name in archive.namelist():
        if not re.match(r"xl/worksheets/sheet\d+\.xml$", member_name):
            continue
        sheet_root = ET.fromstring(archive.read(member_name))
        for value_node in sheet_root.findall(f".//{_qn('x:v')}"):
            cell_text = (value_node.text or "").strip()
            if not cell_text:
                continue
            if value_node.getparent if False else None:
                pass
            text_parts.append(cell_text)
            if len(text_parts) >= MAX_TEXT_PARTS:
                break
        if len(text_parts) >= MAX_TEXT_PARTS:
            break

    # Replace shared-string indexes where possible.
    normalized_parts: list[str] = []
    for member_name in archive.namelist():
        if not re.match(r"xl/worksheets/sheet\d+\.xml$", member_name):
            continue
        sheet_root = ET.fromstring(archive.read(member_name))
        for cell in sheet_root.findall(f".//{_qn('x:c')}"):
            value_node = cell.find(_qn("x:v"))
            if value_node is None or not (value_node.text or "").strip():
                continue
            raw_value = value_node.text.strip()
            if cell.attrib.get("t") == "s":
                try:
                    normalized_parts.append(shared_strings[int(raw_value)])
                except (ValueError, IndexError):
                    normalized_parts.append(raw_value)
            else:
                normalized_parts.append(raw_value)
            if len(normalized_parts) >= MAX_TEXT_PARTS:
                break
        if len(normalized_parts) >= MAX_TEXT_PARTS:
            break
    return (normalized_parts or text_parts, sheet_names[:MAX_HEADING_COUNT])


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except (KeyError, ET.ParseError):
        return []
    strings: list[str] = []
    for item in root.findall(f".//{_qn('x:si')}"):
        text = "".join(node.text or "" for node in item.findall(f".//{_qn('x:t')}")).strip()
        strings.append(text)
    return strings


def _pptx_text_and_headings(archive: zipfile.ZipFile) -> tuple[list[str], list[str]]:
    slide_members = sorted(
        member_name
        for member_name in archive.namelist()
        if re.match(r"ppt/slides/slide\d+\.xml$", member_name)
    )
    text_parts: list[str] = []
    headings: list[str] = []
    for member_name in slide_members:
        root = ET.fromstring(archive.read(member_name))
        slide_text = _xml_text_parts(root)
        if slide_text:
            headings.append(slide_text[0])
            text_parts.extend(slide_text)
        if len(text_parts) >= MAX_TEXT_PARTS:
            break
    return (text_parts[:MAX_TEXT_PARTS], headings[:MAX_HEADING_COUNT])


def _xml_text_parts(root: ET.Element) -> list[str]:
    parts: list[str] = []
    for node in root.iter():
        text = (node.text or "").strip()
        if text:
            parts.append(text)
        if len(parts) >= MAX_TEXT_PARTS:
            break
    return parts


def _qn(name: str) -> str:
    prefix, tag = name.split(":", 1)
    namespaces = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    }
    return f"{{{namespaces[prefix]}}}{tag}"


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
        ".doc": "doc",
        ".docx": "docx",
        ".docm": "docx",
        ".xls": "xls",
        ".xlsx": "xlsx",
        ".xlsm": "xlsx",
        ".ppt": "ppt",
        ".pptx": "pptx",
        ".pptm": "pptx",
        ".odt": "odt",
        ".ods": "ods",
        ".odp": "odp",
        ".odg": "odg",
    }.get(extension, extension.lstrip(".") or "file")


def _extract_headings(lines: list[str], extension: str) -> list[str]:
    headings: list[str] = []
    if extension == ".json":
        try:
            parsed = json.loads("\n".join(lines))
            if isinstance(parsed, dict):
                headings = [str(key) for key in list(parsed.keys())[:MAX_HEADING_COUNT]]
        except json.JSONDecodeError:
            headings = []
    elif extension == ".csv":
        try:
            reader = csv.reader(lines)
            header = next(reader, [])
            headings = [item.strip() for item in header if item.strip()][:MAX_HEADING_COUNT]
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
            if len(headings) >= MAX_HEADING_COUNT:
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
