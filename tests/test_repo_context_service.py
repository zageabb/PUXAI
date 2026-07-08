from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from app.services.repo_context_service import ingest_repository_context, list_repository_files, read_document_summary


def test_repo_context_handles_small_folder_and_ignores_unwanted_dirs(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("from flask import Flask\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n\nSome context\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "skip.js").write_text("ignored", encoding="utf-8")

    files = list_repository_files(tmp_path)
    context = ingest_repository_context(str(tmp_path), "*.py,*.md", "notes")

    assert "node_modules/skip.js" not in files
    assert any(path.endswith("main.py") for path in context["selected_files"])
    assert context["summary"]


def test_read_document_summary_reads_text_file(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("# Heading\n\nSome useful details\n", encoding="utf-8")

    result = read_document_summary(path)

    assert result["kind"] == "md"
    assert "Heading" in result["headings"][0]
    assert "Markdown attachment" in result["summary"]


def test_read_document_summary_reads_docx_file(tmp_path: Path) -> None:
    path = tmp_path / "notes.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>Docx heading</w:t></w:r></w:p></w:body></w:document>"
            ),
        )

    result = read_document_summary(path)

    assert result["kind"] == "docx"
    assert "Word document" in result["summary"]


def test_ingest_repository_context_rejects_missing_or_non_directory_paths(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="does not exist"):
        ingest_repository_context(str(tmp_path / "missing"), "*.py", "")

    with pytest.raises(ValueError, match="not a directory"):
        ingest_repository_context(str(file_path), "*.py", "")
