from datetime import datetime, timezone

from nuclear_energy.db import DocumentExportRow
from nuclear_energy.exports import documents_to_csv, documents_to_markdown


def test_documents_to_csv_writes_header_and_rows():
    exported = documents_to_csv([_document()])

    assert "title,url,source_name,source_kind,published_at,summary,content_preview,chunk_count,embedded_chunk_count" in exported
    assert "Reactor update,https://example.com/reactor,Example,rss,2026-08-13T12:00:00+00:00" in exported


def test_documents_to_markdown_writes_document_sections():
    exported = documents_to_markdown([_document()])

    assert "# Nuclear Energy Document Export" in exported
    assert "## Reactor update" in exported
    assert "- URL: https://example.com/reactor" in exported
    assert "Short summary" in exported
    assert "Longer content preview" in exported


def _document() -> DocumentExportRow:
    return DocumentExportRow(
        title="Reactor update",
        url="https://example.com/reactor",
        source_name="Example",
        source_kind="rss",
        published_at=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc),
        summary="Short summary",
        content_preview="Longer content preview",
        chunk_count=2,
        embedded_chunk_count=1,
    )
