from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, Table, Text, UniqueConstraint, create_engine
from sqlalchemy import delete, select, text as sql_text, update
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nuclear_energy.config import get_settings
from nuclear_energy.models import RawDocument


metadata = MetaData(schema="public")

document_source_kind = ENUM(
    "rss",
    "gdelt",
    "eur_lex",
    "congress",
    "federal_register",
    "regulations_gov",
    name="document_source_kind",
    schema="public",
    create_type=False,
)


@dataclass(frozen=True)
class StoredDocument:
    id: str
    title: str
    url: str
    content: str | None = None
    summary: str | None = None


ingested_documents = Table(
    "ingested_documents",
    metadata,
    # Reflected manually because the database is migration-owned.
    # SQLAlchemy only needs these columns for upserts.
    Column("id", UUID(as_uuid=False), primary_key=True, server_default=sql_text("extensions.gen_random_uuid()")),
    Column("source_kind", document_source_kind, nullable=False),
    Column("source_name", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("published_at", DateTime(timezone=True)),
    Column("summary", Text),
    Column("content", Text),
    Column("authors", JSON, nullable=False),
    Column("tags", JSON, nullable=False),
    Column("raw_payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_kind", "external_id", name="ingested_documents_source_external_unique"),
)

document_chunks = Table(
    "document_chunks",
    metadata,
    Column("document_id", UUID(as_uuid=False), nullable=False),
    Column("chunk_index", Integer, nullable=False),
    Column("content", Text, nullable=False),
    Column("token_count", Integer),
    Column("embedding_model", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("document_id", "chunk_index", name="document_chunks_document_chunk_unique"),
)


def get_engine():
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for database writes.")
    return create_engine(settings.database_url, pool_pre_ping=True)


def upsert_documents(documents: Iterable[RawDocument]) -> int:
    rows = []
    now = datetime.now(timezone.utc)
    for document in documents:
        payload = document.model_dump(mode="json")
        rows.append(
            {
                "source_kind": document.source_kind.value,
                "source_name": document.source_name,
                "external_id": document.external_id,
                "title": document.title,
                "url": document.url_text,
                "published_at": document.published_at,
                "summary": document.summary,
                "content": document.content,
                "authors": document.authors,
                "tags": document.tags,
                "raw_payload": payload,
                "updated_at": now,
            }
        )

    if not rows:
        return 0

    statement = insert(ingested_documents).values(rows)
    update_columns = {
        column.name: getattr(statement.excluded, column.name)
        for column in ingested_documents.c
        if column.name not in {"source_kind", "external_id"}
    }

    with Session(get_engine()) as session:
        session.execute(
            statement.on_conflict_do_update(
                index_elements=["source_kind", "external_id"],
                set_=update_columns,
            )
        )
        session.commit()

    return len(rows)


def fetch_documents_without_chunks(limit: int = 10, source_name: Optional[str] = None) -> list[StoredDocument]:
    chunk_exists = (
        select(document_chunks.c.document_id)
        .where(document_chunks.c.document_id == ingested_documents.c.id)
        .exists()
    )
    conditions = [~chunk_exists]
    if source_name:
        conditions.append(ingested_documents.c.source_name == source_name)

    statement = (
        select(
            ingested_documents.c.id,
            ingested_documents.c.title,
            ingested_documents.c.url,
            ingested_documents.c.content,
            ingested_documents.c.summary,
        )
        .where(*conditions)
        .order_by(
            ingested_documents.c.published_at.desc().nulls_last(),
            ingested_documents.c.created_at.desc(),
        )
        .limit(limit)
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement).mappings().all()

    return [
        StoredDocument(
            id=str(row["id"]),
            title=row["title"],
            url=row["url"],
            content=row["content"],
            summary=row["summary"],
        )
        for row in rows
    ]


def replace_document_chunks(document_id: str, content: str, chunks: Sequence[str]) -> int:
    if not chunks:
        return 0

    now = datetime.now(timezone.utc)
    rows = [
        {
            "document_id": document_id,
            "chunk_index": index,
            "content": chunk,
            "token_count": _estimate_token_count(chunk),
            "updated_at": now,
        }
        for index, chunk in enumerate(chunks)
    ]

    with Session(get_engine()) as session:
        session.execute(
            update(ingested_documents)
            .where(ingested_documents.c.id == document_id)
            .values(content=content, updated_at=now)
        )
        session.execute(delete(document_chunks).where(document_chunks.c.document_id == document_id))
        session.execute(insert(document_chunks).values(rows))
        session.commit()

    return len(rows)


def _estimate_token_count(text: str) -> int:
    return max(1, len(text.split()))
