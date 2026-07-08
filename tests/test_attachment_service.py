from __future__ import annotations

from pathlib import Path
import zipfile

from app.services.attachment_service import summarise_attachment


def test_summarise_docx_attachment(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>"
                "<w:p><w:r><w:t>Project Heading</w:t></w:r></w:p>"
                "<w:p><w:r><w:t>Document body text.</w:t></w:r></w:p>"
                "</w:body></w:document>"
            ),
        )

    result = summarise_attachment(path)

    assert result["kind"] == "docx"
    assert "Word document" in result["summary"]
    assert "Project Heading" in result["preview"]


def test_summarise_xlsx_attachment(tmp_path: Path) -> None:
    path = tmp_path / "sample.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheets><sheet name="SheetOne" sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
                "</sheets></workbook>"
            ),
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<si><t>Header</t></si><si><t>Value</t></si></sst>"
            ),
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row></sheetData>'
                "</worksheet>"
            ),
        )

    result = summarise_attachment(path)

    assert result["kind"] == "xlsx"
    assert "Spreadsheet workbook" in result["summary"]
    assert result["headings"][0] == "SheetOne"
    assert "Header" in result["preview"]


def test_summarise_odt_attachment(tmp_path: Path) -> None:
    path = tmp_path / "sample.odt"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "content.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<office:document-content '
                'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
                'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
                "<office:body><office:text>"
                "<text:h>ODT Heading</text:h><text:p>LibreOffice body text.</text:p>"
                "</office:text></office:body></office:document-content>"
            ),
        )

    result = summarise_attachment(path)

    assert result["kind"] == "odt"
    assert "LibreOffice Writer document" in result["summary"]
    assert "ODT Heading" in result["preview"]
