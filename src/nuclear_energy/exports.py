from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import datetime
from io import StringIO

from nuclear_energy.db import DocumentExportRow


EXPORT_COLUMNS = [
    "title",
    "url",
    "source_name",
    "source_kind",
    "published_at",
    "summary",
    "content_preview",
    "chunk_count",
    "embedded_chunk_count",
]


def documents_to_csv(documents: Sequence[DocumentExportRow]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()
    for document in documents:
        writer.writerow(_document_to_dict(document))
    return output.getvalue()


def documents_to_markdown(documents: Sequence[DocumentExportRow]) -> str:
    lines = ["# Nuclear Energy Document Export", "", f"Documents: {len(documents)}", ""]

    for document in documents:
        lines.extend(
            [
                f"## {document.title}",
                "",
                f"- Source: {document.source_name} ({document.source_kind})",
                f"- Published: {_format_datetime(document.published_at)}",
                f"- URL: {document.url}",
                f"- Chunks: {document.chunk_count}",
                f"- Embedded chunks: {document.embedded_chunk_count}",
                "",
            ]
        )
        if document.summary:
            lines.extend(["### Summary", "", document.summary.strip(), ""])
        if document.content_preview:
            lines.extend(["### Content Preview", "", document.content_preview.strip(), ""])

    return "\n".join(lines).rstrip() + "\n"


def _document_to_dict(document: DocumentExportRow) -> dict[str, object]:
    return {
        "title": document.title,
        "url": document.url,
        "source_name": document.source_name,
        "source_kind": document.source_kind,
        "published_at": _format_datetime(document.published_at),
        "summary": document.summary,
        "content_preview": document.content_preview,
        "chunk_count": document.chunk_count,
        "embedded_chunk_count": document.embedded_chunk_count,
    }


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()
