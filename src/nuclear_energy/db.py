from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, MetaData, Table, Text, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import ENUM
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

ingested_documents = Table(
    "ingested_documents",
    metadata,
    # Reflected manually because the database is migration-owned.
    # SQLAlchemy only needs these columns for upserts.
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
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_kind", "external_id", name="ingested_documents_source_external_unique"),
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
