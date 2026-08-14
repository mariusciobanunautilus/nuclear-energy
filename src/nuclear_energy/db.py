from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, Numeric, Table, Text, UniqueConstraint, create_engine
from sqlalchemy import delete, select, text as sql_text, update
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nuclear_energy.config import get_settings
from nuclear_energy.models import CountryEnergyYear, NuclearTransaction, RawDocument


metadata = MetaData(schema="public")

document_source_kind = ENUM(
    "rss",
    "gdelt",
    "eur_lex",
    "congress",
    "federal_register",
    "regulations_gov",
    "usaspending",
    "eu_ted",
    "sec_edgar",
    "iaea_pris",
    "eia",
    "entsoe",
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


@dataclass(frozen=True)
class StoredChunk:
    id: str
    document_id: str
    title: str
    url: str
    chunk_index: int
    content: str


@dataclass(frozen=True)
class ChunkSearchResult:
    title: str
    url: str
    chunk_index: int
    content: str
    score: float


@dataclass(frozen=True)
class DashboardMetrics:
    document_count: int
    documents_with_content: int
    chunk_count: int
    embedded_chunk_count: int
    source_count: int
    latest_published_at: datetime | None


@dataclass(frozen=True)
class SourceSummary:
    source_name: str
    source_kind: str
    document_count: int
    documents_with_content: int
    chunk_count: int
    embedded_chunk_count: int
    latest_published_at: datetime | None


@dataclass(frozen=True)
class DocumentListItem:
    id: str
    title: str
    url: str
    source_name: str
    source_kind: str
    published_at: datetime | None
    preview: str
    chunk_count: int
    embedded_chunk_count: int


@dataclass(frozen=True)
class KeywordSearchResult:
    id: str
    title: str
    url: str
    source_name: str
    source_kind: str
    published_at: datetime | None
    snippet: str
    score: float


@dataclass(frozen=True)
class DocumentExportRow:
    title: str
    url: str
    source_name: str
    source_kind: str
    published_at: datetime | None
    summary: str
    content_preview: str
    chunk_count: int
    embedded_chunk_count: int


@dataclass(frozen=True)
class EnergySystemMetrics:
    country_count: int
    latest_year: int | None
    nuclear_generation_twh: float | None
    nuclear_capacity_gw: float | None
    electricity_generation_twh: float | None
    electricity_demand_twh: float | None
    net_electricity_imports_twh: float | None


@dataclass(frozen=True)
class EnergyCountrySummary:
    iso_code: str
    country_name: str
    latest_year: int
    nuclear_generation_twh: float | None
    nuclear_share_electricity_percent: float | None
    nuclear_capacity_gw: float | None
    electricity_generation_twh: float | None
    electricity_demand_twh: float | None
    net_electricity_imports_twh: float | None
    estimated_capacity_factor_percent: float | None


@dataclass(frozen=True)
class EnergyYearRecord:
    iso_code: str
    country_name: str
    year: int
    nuclear_generation_twh: float | None
    nuclear_share_electricity_percent: float | None
    nuclear_capacity_gw: float | None
    electricity_generation_twh: float | None
    electricity_demand_twh: float | None
    net_electricity_imports_twh: float | None
    fossil_generation_twh: float | None
    renewables_generation_twh: float | None
    clean_generation_twh: float | None
    estimated_capacity_factor_percent: float | None


@dataclass(frozen=True)
class TransactionDetectionDocument:
    id: str
    title: str
    url: str
    source_name: str
    source_kind: str
    published_at: datetime | None
    summary: str | None
    content: str | None


@dataclass(frozen=True)
class TransactionMetrics:
    transaction_count: int
    country_count: int
    with_amount_count: int
    latest_transaction_date: datetime | None


@dataclass(frozen=True)
class TransactionCountrySummary:
    country_iso_code: str
    country_name: str
    transaction_count: int
    with_amount_count: int
    latest_transaction_date: datetime | None


@dataclass(frozen=True)
class TransactionTypeSummary:
    transaction_type: str
    transaction_count: int
    with_amount_count: int


@dataclass(frozen=True)
class TransactionYearSummary:
    year: int
    transaction_count: int
    with_amount_count: int


@dataclass(frozen=True)
class TransactionListItem:
    id: str
    transaction_date: datetime | None
    country_iso_code: str | None
    country_name: str | None
    plant_name: str | None
    transaction_type: str
    stage: str
    title: str
    summary: str
    amount_text: str | None
    currency: str | None
    confidence: float
    source_name: str
    source_url: str


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
    Column("id", UUID(as_uuid=False), primary_key=True, server_default=sql_text("extensions.gen_random_uuid()")),
    Column("document_id", UUID(as_uuid=False), nullable=False),
    Column("chunk_index", Integer, nullable=False),
    Column("content", Text, nullable=False),
    Column("token_count", Integer),
    Column("embedding_model", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("document_id", "chunk_index", name="document_chunks_document_chunk_unique"),
)

country_energy_years = Table(
    "country_energy_years",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, server_default=sql_text("extensions.gen_random_uuid()")),
    Column("iso_code", Text, nullable=False),
    Column("country_name", Text, nullable=False),
    Column("year", Integer, nullable=False),
    Column("nuclear_generation_twh", Numeric(12, 3)),
    Column("nuclear_share_electricity_percent", Numeric(6, 3)),
    Column("nuclear_capacity_gw", Numeric(12, 3)),
    Column("electricity_generation_twh", Numeric(12, 3)),
    Column("electricity_demand_twh", Numeric(12, 3)),
    Column("net_electricity_imports_twh", Numeric(12, 3)),
    Column("fossil_generation_twh", Numeric(12, 3)),
    Column("renewables_generation_twh", Numeric(12, 3)),
    Column("clean_generation_twh", Numeric(12, 3)),
    Column("source_name", Text, nullable=False),
    Column("source_url", Text, nullable=False),
    Column("raw_payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("iso_code", "year", name="country_energy_years_iso_year_unique"),
)

nuclear_transactions = Table(
    "nuclear_transactions",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, server_default=sql_text("extensions.gen_random_uuid()")),
    Column("external_id", Text, nullable=False),
    Column("document_id", UUID(as_uuid=False), nullable=False),
    Column("transaction_date", DateTime(timezone=True)),
    Column("country_iso_code", Text),
    Column("country_name", Text),
    Column("plant_name", Text),
    Column("project_name", Text),
    Column("transaction_type", Text, nullable=False),
    Column("stage", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("source_name", Text, nullable=False),
    Column("source_url", Text, nullable=False),
    Column("amount_text", Text),
    Column("amount", Numeric(18, 2)),
    Column("currency", Text),
    Column("counterparties", JSON, nullable=False),
    Column("matched_terms", JSON, nullable=False),
    Column("confidence", Numeric(4, 3), nullable=False),
    Column("raw_payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("external_id", name="nuclear_transactions_external_id_unique"),
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


def upsert_country_energy_years(records: Iterable[CountryEnergyYear]) -> int:
    rows = []
    now = datetime.now(timezone.utc)
    for record in records:
        rows.append(
            {
                "iso_code": record.iso_code.upper(),
                "country_name": record.country_name,
                "year": record.year,
                "nuclear_generation_twh": record.nuclear_generation_twh,
                "nuclear_share_electricity_percent": record.nuclear_share_electricity_percent,
                "nuclear_capacity_gw": record.nuclear_capacity_gw,
                "electricity_generation_twh": record.electricity_generation_twh,
                "electricity_demand_twh": record.electricity_demand_twh,
                "net_electricity_imports_twh": record.net_electricity_imports_twh,
                "fossil_generation_twh": record.fossil_generation_twh,
                "renewables_generation_twh": record.renewables_generation_twh,
                "clean_generation_twh": record.clean_generation_twh,
                "source_name": record.source_name,
                "source_url": record.source_url,
                "raw_payload": record.raw_payload,
                "updated_at": now,
            }
        )

    if not rows:
        return 0

    statement = insert(country_energy_years).values(rows)
    update_columns = {
        column: getattr(statement.excluded, column)
        for column in rows[0]
        if column not in {"iso_code", "year"}
    }

    with Session(get_engine()) as session:
        session.execute(
            statement.on_conflict_do_update(
                index_elements=["iso_code", "year"],
                set_=update_columns,
            )
        )
        session.commit()

    return len(rows)


def upsert_nuclear_transactions(transactions: Iterable[NuclearTransaction]) -> int:
    rows = []
    now = datetime.now(timezone.utc)
    for transaction in transactions:
        rows.append(
            {
                "external_id": transaction.external_id,
                "document_id": transaction.document_id,
                "transaction_date": transaction.transaction_date,
                "country_iso_code": transaction.country_iso_code.upper() if transaction.country_iso_code else None,
                "country_name": transaction.country_name,
                "plant_name": transaction.plant_name,
                "project_name": transaction.project_name,
                "transaction_type": transaction.transaction_type,
                "stage": transaction.stage,
                "title": transaction.title,
                "summary": transaction.summary,
                "source_name": transaction.source_name,
                "source_url": transaction.source_url,
                "amount_text": transaction.amount_text,
                "amount": transaction.amount,
                "currency": transaction.currency,
                "counterparties": transaction.counterparties,
                "matched_terms": transaction.matched_terms,
                "confidence": transaction.confidence,
                "raw_payload": transaction.raw_payload,
                "updated_at": now,
            }
        )

    if not rows:
        return 0

    statement = insert(nuclear_transactions).values(rows)
    update_columns = {
        column: getattr(statement.excluded, column)
        for column in rows[0]
        if column != "external_id"
    }

    with Session(get_engine()) as session:
        session.execute(
            statement.on_conflict_do_update(
                index_elements=["external_id"],
                set_=update_columns,
            )
        )
        session.commit()

    return len(rows)


def fetch_document_id_map(document_keys: Iterable[tuple[str, str]]) -> dict[tuple[str, str], str]:
    keys = list(dict.fromkeys(document_keys))
    if not keys:
        return {}

    conditions = []
    params: dict[str, object] = {}
    for index, (source_kind, external_id) in enumerate(keys):
        conditions.append(
            f"""
            (
              source_kind = cast(:source_kind_{index} as public.document_source_kind)
              and external_id = :external_id_{index}
            )
            """
        )
        params[f"source_kind_{index}"] = source_kind
        params[f"external_id_{index}"] = external_id

    statement = sql_text(
        f"""
        select id, source_kind::text as source_kind, external_id
        from public.ingested_documents
        where {" or ".join(conditions)}
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()

    return {
        (row["source_kind"], row["external_id"]): str(row["id"])
        for row in rows
    }


def delete_detected_nuclear_transactions(source_name: Optional[str] = None) -> int:
    conditions = ["stage = 'detected'"]
    params: dict[str, object] = {}
    if source_name:
        conditions.append("source_name = :source_name")
        params["source_name"] = source_name

    statement = sql_text(
        f"""
        delete from public.nuclear_transactions
        {_where_clause(conditions)}
        """
    )

    with Session(get_engine()) as session:
        result = session.execute(statement, params)
        session.commit()

    return int(result.rowcount or 0)


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


def fetch_dashboard_metrics() -> DashboardMetrics:
    statement = sql_text(
        """
        select
          (select count(*) from public.ingested_documents) as document_count,
          (
            select count(*)
            from public.ingested_documents
            where nullif(content, '') is not null
          ) as documents_with_content,
          (select count(*) from public.document_chunks) as chunk_count,
          (
            select count(*)
            from public.document_chunks
            where embedding is not null
          ) as embedded_chunk_count,
          (select count(distinct source_name) from public.ingested_documents) as source_count,
          (select max(published_at) from public.ingested_documents) as latest_published_at
        """
    )

    with Session(get_engine()) as session:
        row = session.execute(statement).mappings().one()

    return DashboardMetrics(
        document_count=int(row["document_count"]),
        documents_with_content=int(row["documents_with_content"]),
        chunk_count=int(row["chunk_count"]),
        embedded_chunk_count=int(row["embedded_chunk_count"]),
        source_count=int(row["source_count"]),
        latest_published_at=row["latest_published_at"],
    )


def fetch_source_summaries() -> list[SourceSummary]:
    statement = sql_text(
        """
        with chunk_counts as (
          select
            document_id,
            count(*) as chunk_count,
            count(*) filter (where embedding is not null) as embedded_chunk_count
          from public.document_chunks
          group by document_id
        )
        select
          d.source_name,
          d.source_kind::text as source_kind,
          count(*) as document_count,
          count(*) filter (where nullif(d.content, '') is not null) as documents_with_content,
          coalesce(sum(chunk_counts.chunk_count), 0) as chunk_count,
          coalesce(sum(chunk_counts.embedded_chunk_count), 0) as embedded_chunk_count,
          max(d.published_at) as latest_published_at
        from public.ingested_documents as d
        left join chunk_counts
          on chunk_counts.document_id = d.id
        group by d.source_name, d.source_kind
        order by document_count desc, d.source_name
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement).mappings().all()

    return [
        SourceSummary(
            source_name=row["source_name"],
            source_kind=row["source_kind"],
            document_count=int(row["document_count"]),
            documents_with_content=int(row["documents_with_content"]),
            chunk_count=int(row["chunk_count"]),
            embedded_chunk_count=int(row["embedded_chunk_count"]),
            latest_published_at=row["latest_published_at"],
        )
        for row in rows
    ]


def fetch_recent_documents(
    *,
    limit: int = 25,
    source_name: Optional[str] = None,
    preview_chars: int = 320,
) -> list[DocumentListItem]:
    if limit < 1:
        return []

    preview_chars = max(1, preview_chars)
    conditions = []
    params: dict[str, object] = {"limit": limit, "preview_chars": preview_chars}
    if source_name:
        conditions.append("d.source_name = :source_name")
        params["source_name"] = source_name

    statement = sql_text(
        f"""
        with chunk_counts as (
          select
            document_id,
            count(*) as chunk_count,
            count(*) filter (where embedding is not null) as embedded_chunk_count
          from public.document_chunks
          group by document_id
        )
        select
          d.id,
          d.title,
          d.url,
          d.source_name,
          d.source_kind::text as source_kind,
          d.published_at,
          left(coalesce(nullif(d.summary, ''), nullif(d.content, ''), ''), :preview_chars) as preview,
          coalesce(chunk_counts.chunk_count, 0) as chunk_count,
          coalesce(chunk_counts.embedded_chunk_count, 0) as embedded_chunk_count
        from public.ingested_documents as d
        left join chunk_counts
          on chunk_counts.document_id = d.id
        {_where_clause(conditions)}
        order by d.published_at desc nulls last, d.created_at desc
        limit :limit
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()

    return [
        DocumentListItem(
            id=str(row["id"]),
            title=row["title"],
            url=row["url"],
            source_name=row["source_name"],
            source_kind=row["source_kind"],
            published_at=row["published_at"],
            preview=row["preview"] or "",
            chunk_count=int(row["chunk_count"]),
            embedded_chunk_count=int(row["embedded_chunk_count"]),
        )
        for row in rows
    ]


def fetch_documents_for_transaction_detection(
    *,
    limit: int = 500,
    source_name: Optional[str] = None,
) -> list[TransactionDetectionDocument]:
    if limit < 1:
        return []

    conditions = ["d.source_kind::text not in ('usaspending', 'eu_ted')"]
    params: dict[str, object] = {"limit": limit}
    if source_name:
        conditions.append("d.source_name = :source_name")
        params["source_name"] = source_name

    statement = sql_text(
        f"""
        select
          d.id,
          d.title,
          d.url,
          d.source_name,
          d.source_kind::text as source_kind,
          d.published_at,
          d.summary,
          d.content
        from public.ingested_documents as d
        {_where_clause(conditions)}
        order by d.published_at desc nulls last, d.created_at desc
        limit :limit
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()

    return [
        TransactionDetectionDocument(
            id=str(row["id"]),
            title=row["title"],
            url=row["url"],
            source_name=row["source_name"],
            source_kind=row["source_kind"],
            published_at=row["published_at"],
            summary=row["summary"],
            content=row["content"],
        )
        for row in rows
    ]


def search_documents_keyword(
    query: str,
    *,
    limit: int = 25,
    source_name: Optional[str] = None,
) -> list[KeywordSearchResult]:
    query = query.strip()
    if not query or limit < 1:
        return []

    conditions = ["documents.search_vector @@ q.value"]
    params: dict[str, object] = {"query": query, "limit": limit}
    if source_name:
        conditions.append("documents.source_name = :source_name")
        params["source_name"] = source_name

    statement = sql_text(
        f"""
        with q as (
          select websearch_to_tsquery('english', :query) as value
        ),
        documents as (
          select
            d.id,
            d.title,
            d.url,
            d.source_name,
            d.source_kind::text as source_kind,
            d.published_at,
            d.created_at,
            coalesce(nullif(d.content, ''), nullif(d.summary, ''), d.title) as searchable_text,
            to_tsvector(
              'english',
              concat_ws(' ', d.title, d.summary, d.content)
            ) as search_vector
          from public.ingested_documents as d
        )
        select
          documents.id,
          documents.title,
          documents.url,
          documents.source_name,
          documents.source_kind,
          documents.published_at,
          ts_headline(
            'english',
            documents.searchable_text,
            q.value,
            'MaxWords=34, MinWords=12, ShortWord=3'
          ) as snippet,
          ts_rank_cd(documents.search_vector, q.value) as score
        from documents
        cross join q
        where {" and ".join(conditions)}
        order by score desc, documents.published_at desc nulls last, documents.created_at desc
        limit :limit
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()

    return [
        KeywordSearchResult(
            id=str(row["id"]),
            title=row["title"],
            url=row["url"],
            source_name=row["source_name"],
            source_kind=row["source_kind"],
            published_at=row["published_at"],
            snippet=row["snippet"] or "",
            score=float(row["score"]),
        )
        for row in rows
    ]


def fetch_documents_for_export(
    *,
    limit: int = 100,
    source_name: Optional[str] = None,
    preview_chars: int = 1200,
) -> list[DocumentExportRow]:
    if limit < 1:
        return []

    preview_chars = max(1, preview_chars)
    conditions = []
    params: dict[str, object] = {"limit": limit, "preview_chars": preview_chars}
    if source_name:
        conditions.append("d.source_name = :source_name")
        params["source_name"] = source_name

    statement = sql_text(
        f"""
        with chunk_counts as (
          select
            document_id,
            count(*) as chunk_count,
            count(*) filter (where embedding is not null) as embedded_chunk_count
          from public.document_chunks
          group by document_id
        )
        select
          d.title,
          d.url,
          d.source_name,
          d.source_kind::text as source_kind,
          d.published_at,
          coalesce(d.summary, '') as summary,
          left(coalesce(nullif(d.content, ''), nullif(d.summary, ''), ''), :preview_chars) as content_preview,
          coalesce(chunk_counts.chunk_count, 0) as chunk_count,
          coalesce(chunk_counts.embedded_chunk_count, 0) as embedded_chunk_count
        from public.ingested_documents as d
        left join chunk_counts
          on chunk_counts.document_id = d.id
        {_where_clause(conditions)}
        order by d.published_at desc nulls last, d.created_at desc
        limit :limit
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()

    return [
        DocumentExportRow(
            title=row["title"],
            url=row["url"],
            source_name=row["source_name"],
            source_kind=row["source_kind"],
            published_at=row["published_at"],
            summary=row["summary"] or "",
            content_preview=row["content_preview"] or "",
            chunk_count=int(row["chunk_count"]),
            embedded_chunk_count=int(row["embedded_chunk_count"]),
        )
        for row in rows
    ]


def fetch_energy_system_metrics() -> EnergySystemMetrics:
    statement = sql_text(
        """
        with latest_country_years as (
          select *
          from (
            select
              y.*,
              row_number() over (partition by y.iso_code order by y.year desc) as rank
            from public.country_energy_years as y
          ) ranked
          where rank = 1
        )
        select
          count(*) as country_count,
          max(year) as latest_year,
          sum(nuclear_generation_twh) as nuclear_generation_twh,
          sum(nuclear_capacity_gw) as nuclear_capacity_gw,
          sum(electricity_generation_twh) as electricity_generation_twh,
          sum(electricity_demand_twh) as electricity_demand_twh,
          sum(net_electricity_imports_twh) as net_electricity_imports_twh
        from latest_country_years
        """
    )

    with Session(get_engine()) as session:
        row = session.execute(statement).mappings().one()

    return EnergySystemMetrics(
        country_count=int(row["country_count"]),
        latest_year=row["latest_year"],
        nuclear_generation_twh=_optional_float(row["nuclear_generation_twh"]),
        nuclear_capacity_gw=_optional_float(row["nuclear_capacity_gw"]),
        electricity_generation_twh=_optional_float(row["electricity_generation_twh"]),
        electricity_demand_twh=_optional_float(row["electricity_demand_twh"]),
        net_electricity_imports_twh=_optional_float(row["net_electricity_imports_twh"]),
    )


def fetch_energy_country_summaries(limit: int = 250) -> list[EnergyCountrySummary]:
    if limit < 1:
        return []

    statement = sql_text(
        """
        with latest_country_years as (
          select *
          from (
            select
              y.*,
              row_number() over (partition by y.iso_code order by y.year desc) as rank
            from public.country_energy_years as y
          ) ranked
          where rank = 1
        )
        select
          iso_code,
          country_name,
          year as latest_year,
          nuclear_generation_twh,
          nuclear_share_electricity_percent,
          nuclear_capacity_gw,
          electricity_generation_twh,
          electricity_demand_twh,
          net_electricity_imports_twh
        from latest_country_years
        order by
          nuclear_generation_twh desc nulls last,
          nuclear_capacity_gw desc nulls last,
          country_name
        limit :limit
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, {"limit": limit}).mappings().all()

    return [
        EnergyCountrySummary(
            iso_code=row["iso_code"],
            country_name=row["country_name"],
            latest_year=int(row["latest_year"]),
            nuclear_generation_twh=_optional_float(row["nuclear_generation_twh"]),
            nuclear_share_electricity_percent=_optional_float(row["nuclear_share_electricity_percent"]),
            nuclear_capacity_gw=_optional_float(row["nuclear_capacity_gw"]),
            electricity_generation_twh=_optional_float(row["electricity_generation_twh"]),
            electricity_demand_twh=_optional_float(row["electricity_demand_twh"]),
            net_electricity_imports_twh=_optional_float(row["net_electricity_imports_twh"]),
            estimated_capacity_factor_percent=_capacity_factor_percent(
                _optional_float(row["nuclear_generation_twh"]),
                _optional_float(row["nuclear_capacity_gw"]),
            ),
        )
        for row in rows
    ]


def fetch_energy_years(iso_code: str) -> list[EnergyYearRecord]:
    iso_code = iso_code.strip().upper()
    if not iso_code:
        return []

    statement = sql_text(
        """
        select
          iso_code,
          country_name,
          year,
          nuclear_generation_twh,
          nuclear_share_electricity_percent,
          nuclear_capacity_gw,
          electricity_generation_twh,
          electricity_demand_twh,
          net_electricity_imports_twh,
          fossil_generation_twh,
          renewables_generation_twh,
          clean_generation_twh
        from public.country_energy_years
        where iso_code = :iso_code
        order by year
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, {"iso_code": iso_code}).mappings().all()

    return [
        EnergyYearRecord(
            iso_code=row["iso_code"],
            country_name=row["country_name"],
            year=int(row["year"]),
            nuclear_generation_twh=_optional_float(row["nuclear_generation_twh"]),
            nuclear_share_electricity_percent=_optional_float(row["nuclear_share_electricity_percent"]),
            nuclear_capacity_gw=_optional_float(row["nuclear_capacity_gw"]),
            electricity_generation_twh=_optional_float(row["electricity_generation_twh"]),
            electricity_demand_twh=_optional_float(row["electricity_demand_twh"]),
            net_electricity_imports_twh=_optional_float(row["net_electricity_imports_twh"]),
            fossil_generation_twh=_optional_float(row["fossil_generation_twh"]),
            renewables_generation_twh=_optional_float(row["renewables_generation_twh"]),
            clean_generation_twh=_optional_float(row["clean_generation_twh"]),
            estimated_capacity_factor_percent=_capacity_factor_percent(
                _optional_float(row["nuclear_generation_twh"]),
                _optional_float(row["nuclear_capacity_gw"]),
            ),
        )
        for row in rows
    ]


def fetch_transaction_metrics(country_iso_code: Optional[str] = None) -> TransactionMetrics:
    conditions, params = _transaction_conditions(country_iso_code)
    statement = sql_text(
        f"""
        select
          count(*) as transaction_count,
          count(distinct country_iso_code) filter (where country_iso_code is not null) as country_count,
          count(*) filter (where amount_text is not null) as with_amount_count,
          max(transaction_date) as latest_transaction_date
        from public.nuclear_transactions
        {_where_clause(conditions)}
        """
    )

    with Session(get_engine()) as session:
        row = session.execute(statement, params).mappings().one()

    return TransactionMetrics(
        transaction_count=int(row["transaction_count"]),
        country_count=int(row["country_count"]),
        with_amount_count=int(row["with_amount_count"]),
        latest_transaction_date=row["latest_transaction_date"],
    )


def fetch_transaction_country_summaries(limit: int = 100) -> list[TransactionCountrySummary]:
    if limit < 1:
        return []

    statement = sql_text(
        """
        select
          country_iso_code,
          country_name,
          count(*) as transaction_count,
          count(*) filter (where amount_text is not null) as with_amount_count,
          max(transaction_date) as latest_transaction_date
        from public.nuclear_transactions
        where country_iso_code is not null
        group by country_iso_code, country_name
        order by transaction_count desc, latest_transaction_date desc nulls last, country_name
        limit :limit
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, {"limit": limit}).mappings().all()

    return [
        TransactionCountrySummary(
            country_iso_code=row["country_iso_code"],
            country_name=row["country_name"],
            transaction_count=int(row["transaction_count"]),
            with_amount_count=int(row["with_amount_count"]),
            latest_transaction_date=row["latest_transaction_date"],
        )
        for row in rows
    ]


def fetch_transaction_type_summaries(country_iso_code: Optional[str] = None) -> list[TransactionTypeSummary]:
    conditions, params = _transaction_conditions(country_iso_code)
    statement = sql_text(
        f"""
        select
          transaction_type,
          count(*) as transaction_count,
          count(*) filter (where amount_text is not null) as with_amount_count
        from public.nuclear_transactions
        {_where_clause(conditions)}
        group by transaction_type
        order by transaction_count desc, transaction_type
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()

    return [
        TransactionTypeSummary(
            transaction_type=row["transaction_type"],
            transaction_count=int(row["transaction_count"]),
            with_amount_count=int(row["with_amount_count"]),
        )
        for row in rows
    ]


def fetch_transaction_year_summaries(country_iso_code: Optional[str] = None) -> list[TransactionYearSummary]:
    conditions, params = _transaction_conditions(country_iso_code)
    statement = sql_text(
        f"""
        select
          extract(year from coalesce(transaction_date, created_at))::integer as year,
          count(*) as transaction_count,
          count(*) filter (where amount_text is not null) as with_amount_count
        from public.nuclear_transactions
        {_where_clause(conditions)}
        group by year
        order by year
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()

    return [
        TransactionYearSummary(
            year=int(row["year"]),
            transaction_count=int(row["transaction_count"]),
            with_amount_count=int(row["with_amount_count"]),
        )
        for row in rows
    ]


def fetch_recent_transactions(
    *,
    limit: int = 50,
    country_iso_code: Optional[str] = None,
) -> list[TransactionListItem]:
    if limit < 1:
        return []

    conditions, params = _transaction_conditions(country_iso_code)
    params["limit"] = limit
    statement = sql_text(
        f"""
        select
          id,
          transaction_date,
          country_iso_code,
          country_name,
          plant_name,
          transaction_type,
          stage,
          title,
          summary,
          amount_text,
          currency,
          confidence,
          source_name,
          source_url
        from public.nuclear_transactions
        {_where_clause(conditions)}
        order by transaction_date desc nulls last, created_at desc
        limit :limit
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()

    return [
        TransactionListItem(
            id=str(row["id"]),
            transaction_date=row["transaction_date"],
            country_iso_code=row["country_iso_code"],
            country_name=row["country_name"],
            plant_name=row["plant_name"],
            transaction_type=row["transaction_type"],
            stage=row["stage"],
            title=row["title"],
            summary=row["summary"],
            amount_text=row["amount_text"],
            currency=row["currency"],
            confidence=float(row["confidence"]),
            source_name=row["source_name"],
            source_url=row["source_url"],
        )
        for row in rows
    ]


def fetch_chunks_needing_embeddings(limit: int = 25, model: str | None = None) -> list[StoredChunk]:
    if limit < 1:
        return []

    statement = sql_text(
        """
        select
          c.id,
          c.document_id,
          d.title,
          d.url,
          c.chunk_index,
          c.content
        from public.document_chunks as c
        join public.ingested_documents as d
          on d.id = c.document_id
        where c.embedding is null
          or (
            cast(:model as text) is not null
            and c.embedding_model is distinct from cast(:model as text)
          )
        order by
          d.published_at desc nulls last,
          d.created_at desc,
          c.chunk_index
        limit :limit
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, {"limit": limit, "model": model}).mappings().all()

    return [
        StoredChunk(
            id=str(row["id"]),
            document_id=str(row["document_id"]),
            title=row["title"],
            url=row["url"],
            chunk_index=row["chunk_index"],
            content=row["content"],
        )
        for row in rows
    ]


def update_chunk_embeddings(chunk_embeddings: Iterable[tuple[str, Sequence[float]]], model: str) -> int:
    rows = [(chunk_id, format_vector_literal(embedding)) for chunk_id, embedding in chunk_embeddings]
    if not rows:
        return 0

    statement = sql_text(
        """
        update public.document_chunks
        set
          embedding = cast(:embedding as extensions.vector),
          embedding_model = :model,
          updated_at = now()
        where id = cast(:chunk_id as uuid)
        """
    )

    with Session(get_engine()) as session:
        for chunk_id, embedding in rows:
            session.execute(statement, {"chunk_id": chunk_id, "embedding": embedding, "model": model})
        session.commit()

    return len(rows)


def semantic_search_chunks(
    query_embedding: Sequence[float],
    *,
    limit: int = 5,
    source_name: Optional[str] = None,
) -> list[ChunkSearchResult]:
    if limit < 1:
        return []

    conditions = ["c.embedding is not null"]
    params: dict[str, object] = {
        "embedding": format_vector_literal(query_embedding),
        "limit": limit,
    }
    if source_name:
        conditions.append("d.source_name = :source_name")
        params["source_name"] = source_name

    statement = sql_text(
        f"""
        with query_embedding as (
          select cast(:embedding as extensions.vector) as value
        )
        select
          d.title,
          d.url,
          c.chunk_index,
          c.content,
          1 - (c.embedding <=> query_embedding.value) as score
        from public.document_chunks as c
        join public.ingested_documents as d
          on d.id = c.document_id
        cross join query_embedding
        where {" and ".join(conditions)}
        order by c.embedding <=> query_embedding.value
        limit :limit
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()

    return [
        ChunkSearchResult(
            title=row["title"],
            url=row["url"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            score=float(row["score"]),
        )
        for row in rows
    ]


def format_vector_literal(embedding: Sequence[float]) -> str:
    if not embedding:
        raise ValueError("Embedding must contain at least one value.")

    values = []
    for value in embedding:
        number = float(value)
        if not isfinite(number):
            raise ValueError("Embedding values must be finite numbers.")
        values.append(f"{number:.12g}")

    return f"[{','.join(values)}]"


def _transaction_conditions(country_iso_code: Optional[str]) -> tuple[list[str], dict[str, object]]:
    conditions = []
    params: dict[str, object] = {}
    if country_iso_code:
        conditions.append("country_iso_code = :country_iso_code")
        params["country_iso_code"] = country_iso_code.strip().upper()
    return conditions, params


def _where_clause(conditions: Sequence[str]) -> str:
    if not conditions:
        return ""
    return f"where {' and '.join(conditions)}"


def _capacity_factor_percent(nuclear_generation_twh: float | None, nuclear_capacity_gw: float | None) -> float | None:
    if nuclear_generation_twh is None or nuclear_capacity_gw is None or nuclear_capacity_gw <= 0:
        return None
    return nuclear_generation_twh * 1000 / (nuclear_capacity_gw * 8760) * 100


def _optional_float(value) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not isfinite(number):
        return None
    return number


def _estimate_token_count(text: str) -> int:
    return max(1, len(text.split()))
