from __future__ import annotations

import json
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
from nuclear_energy.models import CountryEnergyYear, NuclearEvent, NuclearTransaction, RawDocument, SourceKind


metadata = MetaData(schema="public")
DOCUMENT_UPSERT_PRESERVED_COLUMNS = {"id", "source_kind", "external_id", "created_at", "ingested_at"}
SOURCE_TIER_LABELS = {
    "tier_1_official_structured": "Tier 1 - Official Structured",
    "tier_2_official_document": "Tier 2 - Official Document",
    "tier_3_company_statement": "Tier 3 - Company Statement",
    "tier_4_reported_media": "Tier 4 - Reported Media",
    "tier_5_discovery_feed": "Tier 5 - Discovery Feed",
    "unclassified": "Unclassified",
}

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
class ReactorTechnologySummary:
    iso_code: str
    country_name: str
    plant_name: str
    reactor_name: str
    reactor_status: str
    technology_code: str | None
    technology_name: str | None
    net_capacity_mwe: int | None
    source_title: str | None
    source_url: str | None


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


@dataclass(frozen=True)
class SourceHealthItem:
    source_name: str
    source_kind: str
    source_tier: str
    document_count: int
    latest_published_at: datetime | None
    latest_seen_at: datetime | None
    latest_run_at: datetime | None
    latest_run_status: str | None
    latest_run_error: str | None


@dataclass(frozen=True)
class EventMetrics:
    event_count: int
    official_event_count: int
    needs_review_count: int
    important_count: int
    duplicate_count: int
    corrected_count: int
    latest_event_date: datetime | None


@dataclass(frozen=True)
class EventListItem:
    id: str
    event_date: datetime | None
    event_type: str
    event_status: str
    review_status: str
    source_tier: str
    country_iso_code: str | None
    country_name: str | None
    project_name: str | None
    title: str
    summary: str
    amount_text: str | None
    materiality_flags: list[str]
    themes: list[str]
    source_confidence: float
    evidence_count: int
    source_name: str | None
    source_url: str | None


@dataclass(frozen=True)
class ReviewQueueItem:
    id: str
    event_date: datetime | None
    event_type: str
    event_status: str
    review_status: str
    source_tier: str
    country_iso_code: str | None
    country_name: str | None
    project_name: str | None
    title: str
    summary: str
    amount_text: str | None
    materiality_flags: list[str]
    themes: list[str]
    source_confidence: float
    evidence_count: int
    source_name: str | None
    source_url: str | None
    review_note: str | None
    duplicate_of_event_id: str | None
    review_priority: int
    review_reasons: list[str]


@dataclass(frozen=True)
class ReviewMetrics:
    queue_count: int
    important_count: int
    corrected_count: int
    duplicate_count: int
    low_confidence_count: int
    official_unreviewed_count: int


@dataclass(frozen=True)
class CompletenessReport:
    document_count: int
    documents_missing_content: int
    documents_without_chunks: int
    chunk_count: int
    chunks_without_embeddings: int
    unclassified_documents: int
    source_count: int
    sources_with_run_history: int
    latest_published_at: datetime | None
    latest_seen_at: datetime | None
    transaction_count: int
    official_transaction_count: int
    event_count: int
    unreviewed_event_count: int
    low_confidence_event_count: int
    review_history_count: int
    energy_country_count: int
    energy_year_count: int
    energy_earliest_year: int | None
    energy_latest_year: int | None
    energy_missing_country_year_count: int


@dataclass(frozen=True)
class SourceCompletenessItem:
    source_name: str
    source_kind: str
    source_tier: str
    document_count: int
    documents_missing_content: int
    documents_without_chunks: int
    chunk_count: int
    chunks_without_embeddings: int
    latest_published_at: datetime | None
    latest_seen_at: datetime | None
    latest_run_at: datetime | None
    latest_run_status: str | None


@dataclass(frozen=True)
class EventEvidenceItem:
    id: str
    event_id: str
    document_id: str | None
    evidence_kind: str
    source_name: str
    source_url: str
    source_tier: str
    published_at: datetime | None
    snippet: str


@dataclass(frozen=True)
class ReviewHistoryItem:
    id: str
    event_id: str
    review_status: str
    previous_status: str | None
    review_action: str
    duplicate_of_event_id: str | None
    patch_payload: dict
    note: str | None
    reviewer: str | None
    created_at: datetime


@dataclass(frozen=True)
class EntitySummary:
    id: str
    canonical_name: str
    entity_type: str
    country_iso_code: str | None
    event_count: int
    latest_event_date: datetime | None
    roles: list[str]


@dataclass(frozen=True)
class ProjectSummary:
    id: str
    canonical_name: str
    project_type: str
    country_iso_code: str | None
    country_name: str | None
    event_count: int
    latest_event_date: datetime | None
    event_types: list[str]


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
    Column("source_tier", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
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
    rows_by_key: dict[tuple[str, str], dict[str, object]] = {}
    now = datetime.now(timezone.utc)
    for document in documents:
        payload = document.model_dump(mode="json")
        source_kind = document.source_kind.value
        rows_by_key[(source_kind, document.external_id)] = {
            "source_kind": source_kind,
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
            "source_tier": source_tier_for_kind(source_kind, document.source_name),
            "ingested_at": now,
            "last_seen_at": now,
            "updated_at": now,
        }

    rows = list(rows_by_key.values())
    if not rows:
        return 0

    statement = insert(ingested_documents).values(rows)
    update_columns = _document_upsert_update_columns(statement)

    with Session(get_engine()) as session:
        session.execute(
            statement.on_conflict_do_update(
                index_elements=["source_kind", "external_id"],
                set_=update_columns,
            )
        )
        session.commit()

    return len(rows)


def _document_upsert_update_columns(statement) -> dict[str, object]:
    return {
        column.name: getattr(statement.excluded, column.name)
        for column in ingested_documents.c
        if column.name not in DOCUMENT_UPSERT_PRESERVED_COLUMNS
    }


OFFICIAL_RSS_SOURCE_MARKERS = (
    "asnr",
    "autorite de surete nucleaire",
    "canadian nuclear safety commission",
    "cnsc",
    "international atomic energy agency",
    "iaea",
    "nuclear regulatory commission",
    "nrc",
    "office for nuclear regulation",
    "onr",
)
COMPANY_RSS_SOURCE_MARKERS = (
    "nuclearelectrica",
    "sn nuclearelectrica",
)


def source_tier_for_kind(source_kind: str | SourceKind, source_name: str | None = None) -> str:
    kind = source_kind.value if isinstance(source_kind, SourceKind) else str(source_kind)
    if kind in {"usaspending", "eu_ted"}:
        return "tier_1_official_structured"
    if kind in {"eur_lex", "federal_register", "congress", "regulations_gov", "iaea_pris", "eia", "entsoe"}:
        return "tier_2_official_document"
    if kind == "rss":
        source = (source_name or "").casefold()
        if any(marker in source for marker in OFFICIAL_RSS_SOURCE_MARKERS):
            return "tier_2_official_document"
        if any(marker in source for marker in COMPANY_RSS_SOURCE_MARKERS):
            return "tier_3_company_statement"
        return "tier_4_reported_media"
    if kind == "gdelt":
        return "tier_5_discovery_feed"
    return "unclassified"


def source_tier_label(source_tier: str | None) -> str:
    return SOURCE_TIER_LABELS.get(source_tier or "unclassified", SOURCE_TIER_LABELS["unclassified"])


def repair_source_tiers() -> dict[str, int]:
    statement = sql_text(
        """
        with document_tiers as (
          select
            id,
            case
              when source_kind::text in ('usaspending', 'eu_ted')
                then 'tier_1_official_structured'
              when source_kind::text in (
                'eur_lex',
                'federal_register',
                'congress',
                'regulations_gov',
                'iaea_pris',
                'eia',
                'entsoe'
              )
                then 'tier_2_official_document'
              when source_kind::text = 'rss'
                and (
                  lower(source_name) like '%international atomic energy agency%'
                  or lower(source_name) like '%iaea%'
                  or lower(source_name) like '%nuclear regulatory commission%'
                  or lower(source_name) like '%nrc%'
                  or lower(source_name) like '%canadian nuclear safety commission%'
                  or lower(source_name) like '%cnsc%'
                  or lower(source_name) like '%office for nuclear regulation%'
                  or lower(source_name) like '%onr%'
                  or lower(source_name) like '%asnr%'
                  or lower(source_name) like '%autorite de surete nucleaire%'
                )
                then 'tier_2_official_document'
              when source_kind::text = 'rss'
                and (
                  lower(source_name) like '%nuclearelectrica%'
                  or lower(source_name) like '%sn nuclearelectrica%'
                )
                then 'tier_3_company_statement'
              when source_kind::text = 'rss'
                then 'tier_4_reported_media'
              when source_kind::text = 'gdelt'
                then 'tier_5_discovery_feed'
              else 'unclassified'
            end as source_tier
          from public.ingested_documents
        ),
        updated_documents as (
          update public.ingested_documents as d
          set
            source_tier = dt.source_tier,
            updated_at = now()
          from document_tiers as dt
          where d.id = dt.id
            and d.source_tier is distinct from dt.source_tier
          returning d.id
        ),
        updated_events as (
          update public.nuclear_events as e
          set
            source_tier = dt.source_tier,
            updated_at = now()
          from public.ingested_documents as d
          join document_tiers as dt
            on dt.id = d.id
          where e.source_document_id = d.id
            and e.source_tier is distinct from dt.source_tier
          returning e.id
        ),
        updated_evidence as (
          update public.event_evidence as ev
          set
            source_tier = dt.source_tier
          from public.ingested_documents as d
          join document_tiers as dt
            on dt.id = d.id
          where ev.document_id = d.id
            and ev.source_tier is distinct from dt.source_tier
          returning ev.id
        )
        select
          (select count(*) from updated_documents) as documents_updated,
          (select count(*) from updated_events) as events_updated,
          (select count(*) from updated_evidence) as evidence_updated
        """
    )

    with Session(get_engine()) as session:
        row = session.execute(statement).mappings().one()
        session.commit()

    return {
        "documents_updated": int(row["documents_updated"]),
        "events_updated": int(row["events_updated"]),
        "evidence_updated": int(row["evidence_updated"]),
    }


def record_ingestion_run(
    *,
    source_kind: str | SourceKind,
    source_name: str,
    status: str,
    documents_seen: int = 0,
    documents_stored: int = 0,
    error_message: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    kind = source_kind.value if isinstance(source_kind, SourceKind) else str(source_kind)
    statement = sql_text(
        """
        insert into public.ingestion_runs (
          source_kind,
          source_name,
          source_tier,
          started_at,
          finished_at,
          status,
          documents_seen,
          documents_stored,
          error_message,
          updated_at
        )
        values (
          cast(:source_kind as public.document_source_kind),
          :source_name,
          :source_tier,
          :started_at,
          :finished_at,
          :status,
          :documents_seen,
          :documents_stored,
          :error_message,
          :updated_at
        )
        """
    )
    with Session(get_engine()) as session:
        session.execute(
            statement,
            {
                "source_kind": kind,
                "source_name": source_name,
                "source_tier": source_tier_for_kind(kind, source_name),
                "started_at": now,
                "finished_at": now,
                "status": status,
                "documents_seen": max(0, documents_seen),
                "documents_stored": max(0, documents_stored),
                "error_message": error_message,
                "updated_at": now,
            },
        )
        session.commit()


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


def sync_events_from_transactions(limit: int | None = None) -> int:
    params: dict[str, object] = {"limit": limit}
    limit_clause = "limit :limit" if limit and limit > 0 else ""
    statement = sql_text(
        f"""
        with transaction_rows as (
          select *
          from public.nuclear_transactions
          order by transaction_date desc nulls last, created_at desc
          {limit_clause}
        ),
        event_rows as (
          select
            t.id as transaction_id,
            'transaction-' || t.external_id as external_id,
            t.document_id as source_document_id,
            case
              when t.stage = 'public_tender' then 'public_tender'
              when t.transaction_type = 'merger_acquisition' then 'm_and_a'
              else t.transaction_type
            end as event_type,
            case
              when t.stage = 'confirmed_award' then 'confirmed'
              when t.stage = 'public_tender' then 'public_tender'
              when t.stage in ('company_announcement', 'regulatory_filing', 'news_reported') then 'reported'
              else 'detected'
            end as event_status,
            case
              when d.source_tier is not null then d.source_tier
              when t.source_name in ('USAspending.gov', 'EU TED') then 'tier_1_official_structured'
              when t.source_name in ('EUR-Lex', 'Federal Register') then 'tier_2_official_document'
              else 'unclassified'
            end as source_tier,
            coalesce(t.transaction_date, t.created_at) as event_date,
            t.country_iso_code,
            t.country_name,
            coalesce(t.project_name, t.plant_name) as project_name,
            t.title,
            t.summary,
            t.amount,
            t.amount_text,
            t.currency,
            jsonb_strip_nulls(jsonb_build_object(
              'large_public_value', case when t.amount >= 50000000 then true end,
              'official_confirmation', case when t.stage in ('confirmed_award', 'public_tender') then true end,
              'public_amount', case when t.amount_text is not null then true end,
              'fuel_cycle_relevance', case when t.transaction_type = 'fuel_supply' then true end,
              'project_stage_change', case when t.stage in ('confirmed_award', 'public_tender') then true end
            )) as flags_object,
            jsonb_strip_nulls(jsonb_build_object(
              'fuel_cycle', case when t.transaction_type = 'fuel_supply' then true end,
              'procurement', case when t.transaction_type in ('contract_award', 'construction_refurbishment') then true end,
              'financing', case when t.transaction_type = 'financing' then true end,
              'm_and_a', case when t.transaction_type = 'merger_acquisition' then true end
            )) as themes_object,
            t.confidence as source_confidence,
            to_jsonb(t) as raw_payload
          from transaction_rows as t
          left join public.ingested_documents as d
            on d.id = t.document_id
        ),
        upserted_events as (
          insert into public.nuclear_events (
            external_id,
            source_document_id,
            event_type,
            event_status,
            source_tier,
            event_date,
            country_iso_code,
            country_name,
            project_name,
            title,
            summary,
            amount,
            amount_text,
            currency,
            materiality_flags,
            themes,
            source_confidence,
            raw_payload,
            last_seen_at,
            updated_at
          )
          select
            external_id,
            source_document_id,
            event_type,
            event_status,
            source_tier,
            event_date,
            country_iso_code,
            country_name,
            project_name,
            title,
            summary,
            amount,
            amount_text,
            currency,
            coalesce((select jsonb_agg(key order by key) from jsonb_each(flags_object) where value = 'true'::jsonb), '[]'::jsonb),
            coalesce((select jsonb_agg(key order by key) from jsonb_each(themes_object) where value = 'true'::jsonb), '[]'::jsonb),
            source_confidence,
            raw_payload,
            now(),
            now()
          from event_rows
          on conflict (external_id) do update
          set
            source_document_id = excluded.source_document_id,
            event_type = excluded.event_type,
            event_status = excluded.event_status,
            source_tier = excluded.source_tier,
            event_date = excluded.event_date,
            country_iso_code = excluded.country_iso_code,
            country_name = excluded.country_name,
            project_name = excluded.project_name,
            title = excluded.title,
            summary = excluded.summary,
            amount = excluded.amount,
            amount_text = excluded.amount_text,
            currency = excluded.currency,
            materiality_flags = excluded.materiality_flags,
            themes = excluded.themes,
            source_confidence = excluded.source_confidence,
            raw_payload = excluded.raw_payload,
            last_seen_at = now(),
            updated_at = now()
          returning id, external_id, source_document_id, source_tier, event_date, summary, raw_payload
        ),
        entity_candidates as (
          select distinct
            btrim(value) as canonical_name,
            'unknown' as entity_type,
            null::text as country_iso_code,
            'mentioned' as role
          from upserted_events e
          cross join lateral jsonb_array_elements_text(e.raw_payload -> 'counterparties') as value
          where btrim(value) <> ''
          union
          select distinct
            btrim(e.raw_payload -> 'raw_payload' ->> 'Recipient Name') as canonical_name,
            'company' as entity_type,
            null::text as country_iso_code,
            'recipient' as role
          from upserted_events e
          where btrim(coalesce(e.raw_payload -> 'raw_payload' ->> 'Recipient Name', '')) <> ''
          union
          select distinct
            btrim(agency_name) as canonical_name,
            'government_agency' as entity_type,
            null::text as country_iso_code,
            'awarding_agency' as role
          from upserted_events e
          cross join lateral (
            values
              (e.raw_payload -> 'raw_payload' ->> 'Awarding Agency'),
              (e.raw_payload -> 'raw_payload' ->> 'Awarding Sub Agency'),
              (e.raw_payload -> 'raw_payload' ->> 'Funding Agency'),
              (e.raw_payload -> 'raw_payload' ->> 'Funding Sub Agency')
          ) agency(agency_name)
          where btrim(coalesce(agency_name, '')) <> ''
        ),
        inserted_entities as (
          insert into public.entities (canonical_name, entity_type, country_iso_code, source_tier, raw_payload)
          select distinct
            canonical_name,
            entity_type,
            country_iso_code,
            'unclassified',
            jsonb_build_object('source', 'transaction_counterparty')
          from entity_candidates
          on conflict (canonical_name) do update
          set
            entity_type = case
              when public.entities.entity_type = 'unknown' then excluded.entity_type
              else public.entities.entity_type
            end,
            country_iso_code = coalesce(public.entities.country_iso_code, excluded.country_iso_code),
            updated_at = now()
          returning id, canonical_name
        ),
        inserted_entity_aliases as (
          insert into public.entity_aliases (entity_id, alias)
          select id, canonical_name
          from inserted_entities
          on conflict do nothing
        ),
        inserted_event_entities as (
          insert into public.event_entities (event_id, entity_id, role)
          select distinct e.id, entities.id, entity_candidates.role
          from upserted_events e
          join entity_candidates
            on true
          join public.entities
            on entities.canonical_name = entity_candidates.canonical_name
          where (
            entity_candidates.canonical_name in (
              select btrim(value)
              from jsonb_array_elements_text(e.raw_payload -> 'counterparties') as value
            )
            or entity_candidates.canonical_name in (
              e.raw_payload -> 'raw_payload' ->> 'Recipient Name',
              e.raw_payload -> 'raw_payload' ->> 'Awarding Agency',
              e.raw_payload -> 'raw_payload' ->> 'Awarding Sub Agency',
              e.raw_payload -> 'raw_payload' ->> 'Funding Agency',
              e.raw_payload -> 'raw_payload' ->> 'Funding Sub Agency'
            )
          )
          on conflict do nothing
        ),
        project_names as (
          select distinct
            btrim(project_name) as canonical_name,
            country_iso_code,
            country_name
          from public.nuclear_events
          where project_name is not null and btrim(project_name) <> ''
        ),
        inserted_projects as (
          insert into public.projects (canonical_name, project_type, country_iso_code, country_name)
          select canonical_name, 'plant', country_iso_code, country_name
          from project_names
          on conflict (canonical_name, country_iso_code) do update
          set
            country_name = excluded.country_name,
            updated_at = now()
          returning id, canonical_name, country_iso_code
        ),
        inserted_project_aliases as (
          insert into public.project_aliases (project_id, alias)
          select id, canonical_name
          from inserted_projects
          on conflict do nothing
        ),
        inserted_event_projects as (
          insert into public.event_projects (event_id, project_id, role)
          select distinct e.id, p.id, 'plant'
          from public.nuclear_events e
          join public.projects p
            on p.canonical_name = e.project_name
            and p.country_iso_code is not distinct from e.country_iso_code
          where e.project_name is not null
          on conflict do nothing
        ),
        inserted_evidence as (
          insert into public.event_evidence (
            event_id,
            document_id,
            evidence_kind,
            source_name,
            source_url,
            source_tier,
            published_at,
            snippet,
            raw_payload
          )
          select
            e.id,
            e.source_document_id,
            'transaction_summary',
            coalesce(e.raw_payload ->> 'source_name', 'Unknown source'),
            coalesce(e.raw_payload ->> 'source_url', 'https://example.invalid'),
            e.source_tier,
            e.event_date,
            left(e.summary, 1200),
            e.raw_payload
          from upserted_events e
          where e.source_document_id is not null
          on conflict (event_id, document_id, evidence_kind) do update
          set
            source_name = excluded.source_name,
            source_url = excluded.source_url,
            source_tier = excluded.source_tier,
            published_at = excluded.published_at,
            snippet = excluded.snippet,
            raw_payload = excluded.raw_payload
        )
        select count(*) as event_count
        from upserted_events
        """
    )

    with Session(get_engine()) as session:
        row = session.execute(statement, params).mappings().one()
        session.commit()

    return int(row["event_count"])


def upsert_nuclear_events(events: Iterable[NuclearEvent]) -> int:
    rows = []
    now = datetime.now(timezone.utc)
    for event in events:
        rows.append(
            {
                "external_id": event.external_id,
                "source_document_id": event.source_document_id,
                "event_type": event.event_type,
                "event_status": event.event_status,
                "source_tier": event.source_tier,
                "event_date": event.event_date,
                "country_iso_code": event.country_iso_code.upper() if event.country_iso_code else None,
                "country_name": event.country_name,
                "project_name": event.project_name,
                "title": event.title,
                "summary": event.summary,
                "amount": event.amount,
                "amount_text": event.amount_text,
                "currency": event.currency,
                "materiality_flags": json.dumps(event.materiality_flags),
                "themes": json.dumps(event.themes),
                "source_confidence": event.source_confidence,
                "raw_payload": json.dumps(event.raw_payload),
                "last_seen_at": now,
                "updated_at": now,
            }
        )

    if not rows:
        return 0

    statement = sql_text(
        """
        insert into public.nuclear_events (
          external_id,
          source_document_id,
          event_type,
          event_status,
          source_tier,
          event_date,
          country_iso_code,
          country_name,
          project_name,
          title,
          summary,
          amount,
          amount_text,
          currency,
          materiality_flags,
          themes,
          source_confidence,
          raw_payload,
          last_seen_at,
          updated_at
        )
        values (
          :external_id,
          cast(:source_document_id as uuid),
          :event_type,
          :event_status,
          :source_tier,
          :event_date,
          :country_iso_code,
          :country_name,
          :project_name,
          :title,
          :summary,
          :amount,
          :amount_text,
          :currency,
          cast(:materiality_flags as jsonb),
          cast(:themes as jsonb),
          :source_confidence,
          cast(:raw_payload as jsonb),
          :last_seen_at,
          :updated_at
        )
        on conflict (external_id) do update
        set
          source_document_id = excluded.source_document_id,
          event_type = excluded.event_type,
          event_status = excluded.event_status,
          source_tier = excluded.source_tier,
          event_date = excluded.event_date,
          country_iso_code = excluded.country_iso_code,
          country_name = excluded.country_name,
          project_name = excluded.project_name,
          title = excluded.title,
          summary = excluded.summary,
          amount = excluded.amount,
          amount_text = excluded.amount_text,
          currency = excluded.currency,
          materiality_flags = excluded.materiality_flags,
          themes = excluded.themes,
          source_confidence = excluded.source_confidence,
          raw_payload = excluded.raw_payload,
          last_seen_at = excluded.last_seen_at,
          updated_at = excluded.updated_at
        returning id, external_id
        """
    )
    evidence_statement = sql_text(
        """
        insert into public.event_evidence (
          event_id,
          document_id,
          evidence_kind,
          source_name,
          source_url,
          source_tier,
          published_at,
          snippet,
          raw_payload
        )
        values (
          cast(:event_id as uuid),
          cast(:document_id as uuid),
          'source_excerpt',
          :source_name,
          :source_url,
          :source_tier,
          :published_at,
          :snippet,
          cast(:raw_payload as jsonb)
        )
        on conflict (event_id, document_id, evidence_kind) do update
        set
          source_name = excluded.source_name,
          source_url = excluded.source_url,
          source_tier = excluded.source_tier,
          published_at = excluded.published_at,
          snippet = excluded.snippet,
          raw_payload = excluded.raw_payload
        """
    )

    by_external_id = {event.external_id: event for event in events}
    with Session(get_engine()) as session:
        event_ids: dict[str, str] = {}
        for row in rows:
            stored = session.execute(statement, row).mappings().one()
            event_ids[str(stored["external_id"])] = str(stored["id"])
        for external_id, event_id in event_ids.items():
            event = by_external_id[external_id]
            session.execute(
                evidence_statement,
                {
                    "event_id": event_id,
                    "document_id": event.source_document_id,
                    "source_name": event.source_name,
                    "source_url": event.source_url,
                    "source_tier": event.source_tier,
                    "published_at": event.event_date,
                    "snippet": event.evidence_snippet,
                    "raw_payload": json.dumps(event.raw_payload),
                },
            )
            _upsert_event_relationships(session, event_id, event)
        session.commit()

    return len(rows)


def sync_event_relationships(limit: int | None = None) -> int:
    params: dict[str, object] = {"limit": limit}
    limit_clause = "limit :limit" if limit and limit > 0 else ""
    statement = sql_text(
        f"""
        with target_events as (
          select *
          from public.nuclear_events
          order by event_date desc nulls last, created_at desc
          {limit_clause}
        ),
        matched_entities as (
          select distinct
            e.id as event_id,
            btrim(entity.canonical_name) as canonical_name,
            coalesce(nullif(entity.entity_type, ''), 'unknown') as entity_type,
            nullif(entity.country_iso_code, '') as country_iso_code,
            'mentioned' as role,
            coalesce(entity.matched_aliases, '') as matched_aliases,
            e.source_tier
          from target_events e
          cross join lateral jsonb_to_recordset(coalesce(e.raw_payload -> 'matched_entities', '[]'::jsonb))
            as entity(canonical_name text, entity_type text, country_iso_code text, matched_aliases text)
          where btrim(coalesce(entity.canonical_name, '')) <> ''
        ),
        counterparty_entities as (
          select distinct
            e.id as event_id,
            btrim(value) as canonical_name,
            'unknown' as entity_type,
            null::text as country_iso_code,
            'mentioned' as role,
            btrim(value) as matched_aliases,
            e.source_tier
          from target_events e
          cross join lateral jsonb_array_elements_text(coalesce(e.raw_payload -> 'counterparties', '[]'::jsonb)) as value
          where btrim(value) <> ''
        ),
        official_entities as (
          select distinct
            e.id as event_id,
            btrim(candidate.name) as canonical_name,
            candidate.entity_type,
            null::text as country_iso_code,
            candidate.role,
            btrim(candidate.name) as matched_aliases,
            e.source_tier
          from target_events e
          cross join lateral (
            values
              (e.raw_payload -> 'raw_payload' ->> 'Recipient Name', 'company', 'recipient'),
              (e.raw_payload -> 'raw_payload' ->> 'Awarding Agency', 'government_agency', 'awarding_agency'),
              (e.raw_payload -> 'raw_payload' ->> 'Awarding Sub Agency', 'government_agency', 'awarding_agency'),
              (e.raw_payload -> 'raw_payload' ->> 'Funding Agency', 'government_agency', 'awarding_agency'),
              (e.raw_payload -> 'raw_payload' ->> 'Funding Sub Agency', 'government_agency', 'awarding_agency')
          ) candidate(name, entity_type, role)
          where btrim(coalesce(candidate.name, '')) <> ''
        ),
        entity_candidates as (
          select * from matched_entities
          union
          select * from counterparty_entities
          union
          select * from official_entities
        ),
        upserted_entities as (
          insert into public.entities (canonical_name, entity_type, country_iso_code, source_tier, raw_payload)
          select distinct
            canonical_name,
            entity_type,
            country_iso_code,
            source_tier,
            jsonb_build_object('source', 'relationship_sync')
          from entity_candidates
          on conflict (canonical_name) do update
          set
            entity_type = case
              when public.entities.entity_type = 'unknown' then excluded.entity_type
              else public.entities.entity_type
            end,
            country_iso_code = coalesce(public.entities.country_iso_code, excluded.country_iso_code),
            source_tier = case
              when public.entities.source_tier = 'unclassified' then excluded.source_tier
              else public.entities.source_tier
            end,
            updated_at = now()
          returning id, canonical_name
        ),
        inserted_aliases as (
          insert into public.entity_aliases (entity_id, alias)
          select distinct entities.id, btrim(alias_value)
          from entity_candidates
          join public.entities
            on entities.canonical_name = entity_candidates.canonical_name
          cross join lateral unnest(
            array_append(string_to_array(entity_candidates.matched_aliases, ','), entity_candidates.canonical_name)
          ) alias(alias_value)
          where btrim(alias_value) <> ''
          on conflict do nothing
        ),
        inserted_event_entities as (
          insert into public.event_entities (event_id, entity_id, role)
          select distinct entity_candidates.event_id, entities.id, entity_candidates.role
          from entity_candidates
          join public.entities
            on entities.canonical_name = entity_candidates.canonical_name
          on conflict do nothing
        ),
        project_candidates as (
          select distinct
            id as event_id,
            btrim(project_name) as canonical_name,
            case
              when event_type in ('fuel_supply', 'sanction_or_export_control') then 'fuel_facility'
              when event_type in ('construction_refurbishment', 'life_extension') then 'life_extension'
              else 'plant'
            end as project_type,
            country_iso_code,
            country_name,
            case
              when event_type in ('license_application', 'license_approval') then 'license_target'
              when event_type = 'fuel_supply' then 'facility'
              else 'plant'
            end as role
          from target_events
          where project_name is not null and btrim(project_name) <> ''
        ),
        upserted_projects as (
          insert into public.projects (canonical_name, project_type, country_iso_code, country_name)
          select canonical_name, project_type, country_iso_code, country_name
          from project_candidates
          on conflict (canonical_name, country_iso_code) do update
          set
            project_type = case
              when public.projects.project_type = 'unknown' then excluded.project_type
              else public.projects.project_type
            end,
            country_name = coalesce(public.projects.country_name, excluded.country_name),
            updated_at = now()
          returning id, canonical_name, country_iso_code
        ),
        inserted_project_aliases as (
          insert into public.project_aliases (project_id, alias)
          select distinct projects.id, project_candidates.canonical_name
          from project_candidates
          join public.projects
            on projects.canonical_name = project_candidates.canonical_name
            and projects.country_iso_code is not distinct from project_candidates.country_iso_code
          on conflict do nothing
        ),
        inserted_event_projects as (
          insert into public.event_projects (event_id, project_id, role)
          select distinct project_candidates.event_id, projects.id, project_candidates.role
          from project_candidates
          join public.projects
            on projects.canonical_name = project_candidates.canonical_name
            and projects.country_iso_code is not distinct from project_candidates.country_iso_code
          on conflict do nothing
        )
        select count(*) as event_count from target_events
        """
    )
    with Session(get_engine()) as session:
        row = session.execute(statement, params).mappings().one()
        session.commit()
    return int(row["event_count"])


def _upsert_event_relationships(session: Session, event_id: str, event: NuclearEvent) -> None:
    for entity in event.raw_payload.get("matched_entities", []):
        canonical_name = str(entity.get("canonical_name") or "").strip()
        if not canonical_name:
            continue
        entity_id = _upsert_entity(
            session,
            canonical_name=canonical_name,
            entity_type=str(entity.get("entity_type") or "unknown"),
            country_iso_code=entity.get("country_iso_code"),
            source_tier=event.source_tier,
            raw_payload={"source": "document_entity_match", "matched_aliases": entity.get("matched_aliases")},
        )
        session.execute(
            sql_text(
                """
                insert into public.event_entities (event_id, entity_id, role)
                values (cast(:event_id as uuid), cast(:entity_id as uuid), 'mentioned')
                on conflict do nothing
                """
            ),
            {"event_id": event_id, "entity_id": entity_id},
        )
        for alias in str(entity.get("matched_aliases") or "").split(","):
            alias = alias.strip()
            if alias:
                _upsert_entity_alias(session, entity_id=entity_id, alias=alias)

    if event.project_name:
        project_id = _upsert_project(
            session,
            canonical_name=event.project_name,
            project_type=_project_type_for_event(event.event_type),
            country_iso_code=event.country_iso_code,
            country_name=event.country_name,
        )
        session.execute(
            sql_text(
                """
                insert into public.event_projects (event_id, project_id, role)
                values (cast(:event_id as uuid), cast(:project_id as uuid), :role)
                on conflict do nothing
                """
            ),
            {
                "event_id": event_id,
                "project_id": project_id,
                "role": _project_role_for_event(event.event_type),
            },
        )
        _upsert_project_alias(session, project_id=project_id, alias=event.project_name)


def _upsert_entity(
    session: Session,
    *,
    canonical_name: str,
    entity_type: str,
    country_iso_code: str | None,
    source_tier: str,
    raw_payload: dict,
) -> str:
    row = session.execute(
        sql_text(
            """
            insert into public.entities (canonical_name, entity_type, country_iso_code, source_tier, raw_payload)
            values (:canonical_name, :entity_type, :country_iso_code, :source_tier, cast(:raw_payload as jsonb))
            on conflict (canonical_name) do update
            set
              entity_type = case
                when public.entities.entity_type = 'unknown' then excluded.entity_type
                else public.entities.entity_type
              end,
              country_iso_code = coalesce(public.entities.country_iso_code, excluded.country_iso_code),
              source_tier = case
                when public.entities.source_tier = 'unclassified' then excluded.source_tier
                else public.entities.source_tier
              end,
              updated_at = now()
            returning id
            """
        ),
        {
            "canonical_name": canonical_name,
            "entity_type": entity_type,
            "country_iso_code": country_iso_code,
            "source_tier": source_tier,
            "raw_payload": json.dumps(raw_payload),
        },
    ).mappings().one()
    entity_id = str(row["id"])
    _upsert_entity_alias(session, entity_id=entity_id, alias=canonical_name)
    return entity_id


def _upsert_entity_alias(session: Session, *, entity_id: str, alias: str) -> None:
    session.execute(
        sql_text(
            """
            insert into public.entity_aliases (entity_id, alias)
            values (cast(:entity_id as uuid), :alias)
            on conflict do nothing
            """
        ),
        {"entity_id": entity_id, "alias": alias},
    )


def _upsert_project(
    session: Session,
    *,
    canonical_name: str,
    project_type: str,
    country_iso_code: str | None,
    country_name: str | None,
) -> str:
    row = session.execute(
        sql_text(
            """
            insert into public.projects (canonical_name, project_type, country_iso_code, country_name)
            values (:canonical_name, :project_type, :country_iso_code, :country_name)
            on conflict (canonical_name, country_iso_code) do update
            set
              project_type = case
                when public.projects.project_type = 'unknown' then excluded.project_type
                else public.projects.project_type
              end,
              country_name = coalesce(public.projects.country_name, excluded.country_name),
              updated_at = now()
            returning id
            """
        ),
        {
            "canonical_name": canonical_name,
            "project_type": project_type,
            "country_iso_code": country_iso_code,
            "country_name": country_name,
        },
    ).mappings().one()
    return str(row["id"])


def _upsert_project_alias(session: Session, *, project_id: str, alias: str) -> None:
    session.execute(
        sql_text(
            """
            insert into public.project_aliases (project_id, alias)
            values (cast(:project_id as uuid), :alias)
            on conflict do nothing
            """
        ),
        {"project_id": project_id, "alias": alias},
    )


def _project_type_for_event(event_type: str) -> str:
    if event_type in {"fuel_supply", "sanction_or_export_control"}:
        return "fuel_facility"
    if event_type in {"construction_refurbishment", "life_extension"}:
        return "life_extension"
    return "plant"


def _project_role_for_event(event_type: str) -> str:
    if event_type in {"license_application", "license_approval"}:
        return "license_target"
    if event_type == "fuel_supply":
        return "facility"
    return "plant"


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


def fetch_completeness_report() -> CompletenessReport:
    statement = sql_text(
        """
        with document_gaps as (
          select
            d.id,
            d.source_name,
            d.source_kind,
            d.source_tier,
            d.published_at,
            d.last_seen_at,
            nullif(d.content, '') is null as missing_content,
            not exists (
              select 1
              from public.document_chunks c
              where c.document_id = d.id
            ) as missing_chunks
          from public.ingested_documents as d
        ),
        energy_bounds as (
          select
            count(distinct iso_code) as country_count,
            count(*) as year_count,
            min(year) as earliest_year,
            max(year) as latest_year
          from public.country_energy_years
        ),
        expected_energy_years as (
          select countries.iso_code, years.year
          from (select distinct iso_code from public.country_energy_years) countries
          cross join lateral generate_series(
            (select earliest_year from energy_bounds),
            (select latest_year from energy_bounds)
          ) as years(year)
          where (select earliest_year from energy_bounds) is not null
            and (select latest_year from energy_bounds) is not null
        )
        select
          (select count(*) from document_gaps) as document_count,
          (select count(*) from document_gaps where missing_content) as documents_missing_content,
          (select count(*) from document_gaps where missing_chunks) as documents_without_chunks,
          (select count(*) from public.document_chunks) as chunk_count,
          (select count(*) from public.document_chunks where embedding is null) as chunks_without_embeddings,
          (select count(*) from document_gaps where source_tier = 'unclassified') as unclassified_documents,
          (select count(distinct source_name) from document_gaps) as source_count,
          (
            select count(distinct source_name)
            from public.ingestion_runs
            where status in ('succeeded', 'failed')
          ) as sources_with_run_history,
          (select max(published_at) from document_gaps) as latest_published_at,
          (select max(last_seen_at) from document_gaps) as latest_seen_at,
          (select count(*) from public.nuclear_transactions) as transaction_count,
          (
            select count(*)
            from public.nuclear_transactions
            where source_name in ('USAspending.gov', 'EU TED')
          ) as official_transaction_count,
          (select count(*) from public.nuclear_events) as event_count,
          (select count(*) from public.nuclear_events where review_status = 'unreviewed') as unreviewed_event_count,
          (select count(*) from public.nuclear_events where source_confidence < 0.7) as low_confidence_event_count,
          (select count(*) from public.event_reviews) as review_history_count,
          coalesce((select country_count from energy_bounds), 0) as energy_country_count,
          coalesce((select year_count from energy_bounds), 0) as energy_year_count,
          (select earliest_year from energy_bounds) as energy_earliest_year,
          (select latest_year from energy_bounds) as energy_latest_year,
          coalesce((
            select count(*)
            from expected_energy_years expected
            left join public.country_energy_years actual
              on actual.iso_code = expected.iso_code
              and actual.year = expected.year
            where actual.id is null
          ), 0) as energy_missing_country_year_count
        """
    )

    with Session(get_engine()) as session:
        row = session.execute(statement).mappings().one()

    return CompletenessReport(
        document_count=int(row["document_count"]),
        documents_missing_content=int(row["documents_missing_content"]),
        documents_without_chunks=int(row["documents_without_chunks"]),
        chunk_count=int(row["chunk_count"]),
        chunks_without_embeddings=int(row["chunks_without_embeddings"]),
        unclassified_documents=int(row["unclassified_documents"]),
        source_count=int(row["source_count"]),
        sources_with_run_history=int(row["sources_with_run_history"]),
        latest_published_at=row["latest_published_at"],
        latest_seen_at=row["latest_seen_at"],
        transaction_count=int(row["transaction_count"]),
        official_transaction_count=int(row["official_transaction_count"]),
        event_count=int(row["event_count"]),
        unreviewed_event_count=int(row["unreviewed_event_count"]),
        low_confidence_event_count=int(row["low_confidence_event_count"]),
        review_history_count=int(row["review_history_count"]),
        energy_country_count=int(row["energy_country_count"]),
        energy_year_count=int(row["energy_year_count"]),
        energy_earliest_year=row["energy_earliest_year"],
        energy_latest_year=row["energy_latest_year"],
        energy_missing_country_year_count=int(row["energy_missing_country_year_count"]),
    )


def fetch_source_completeness() -> list[SourceCompletenessItem]:
    statement = sql_text(
        """
        with chunk_counts as (
          select
            document_id,
            count(*) as chunk_count,
            count(*) filter (where embedding is null) as chunks_without_embeddings
          from public.document_chunks
          group by document_id
        ),
        latest_runs as (
          select *
          from (
            select
              r.source_kind::text as source_kind,
              r.source_name,
              r.finished_at,
              r.status,
              row_number() over (
                partition by r.source_kind, coalesce(r.source_name, '')
                order by r.finished_at desc nulls last, r.started_at desc
              ) as rank
            from public.ingestion_runs as r
          ) ranked
          where rank = 1
        )
        select
          d.source_name,
          d.source_kind::text as source_kind,
          coalesce(max(d.source_tier), 'unclassified') as source_tier,
          count(*) as document_count,
          count(*) filter (where nullif(d.content, '') is null) as documents_missing_content,
          count(*) filter (where coalesce(chunk_counts.chunk_count, 0) = 0) as documents_without_chunks,
          coalesce(sum(chunk_counts.chunk_count), 0) as chunk_count,
          coalesce(sum(chunk_counts.chunks_without_embeddings), 0) as chunks_without_embeddings,
          max(d.published_at) as latest_published_at,
          max(d.last_seen_at) as latest_seen_at,
          latest_runs.finished_at as latest_run_at,
          latest_runs.status as latest_run_status
        from public.ingested_documents as d
        left join chunk_counts
          on chunk_counts.document_id = d.id
        left join latest_runs
          on latest_runs.source_kind = d.source_kind::text
          and coalesce(latest_runs.source_name, '') = coalesce(d.source_name, '')
        group by
          d.source_name,
          d.source_kind,
          latest_runs.finished_at,
          latest_runs.status
        order by document_count desc, d.source_name
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement).mappings().all()

    return [
        SourceCompletenessItem(
            source_name=row["source_name"],
            source_kind=row["source_kind"],
            source_tier=row["source_tier"],
            document_count=int(row["document_count"]),
            documents_missing_content=int(row["documents_missing_content"]),
            documents_without_chunks=int(row["documents_without_chunks"]),
            chunk_count=int(row["chunk_count"]),
            chunks_without_embeddings=int(row["chunks_without_embeddings"]),
            latest_published_at=row["latest_published_at"],
            latest_seen_at=row["latest_seen_at"],
            latest_run_at=row["latest_run_at"],
            latest_run_status=row["latest_run_status"],
        )
        for row in rows
    ]


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


def fetch_source_health() -> list[SourceHealthItem]:
    statement = sql_text(
        """
        with latest_runs as (
          select *
          from (
            select
              r.source_kind::text as source_kind,
              r.source_name,
              r.source_tier,
              r.finished_at,
              r.status,
              r.error_message,
              row_number() over (
                partition by r.source_kind, coalesce(r.source_name, '')
                order by r.finished_at desc nulls last, r.started_at desc
              ) as rank
            from public.ingestion_runs as r
          ) ranked
          where rank = 1
        )
        select
          d.source_name,
          d.source_kind::text as source_kind,
          coalesce(max(d.source_tier), latest_runs.source_tier, 'unclassified') as source_tier,
          count(*) as document_count,
          max(d.published_at) as latest_published_at,
          max(d.last_seen_at) as latest_seen_at,
          latest_runs.finished_at as latest_run_at,
          latest_runs.status as latest_run_status,
          latest_runs.error_message as latest_run_error
        from public.ingested_documents as d
        left join latest_runs
          on latest_runs.source_kind = d.source_kind::text
          and coalesce(latest_runs.source_name, '') = coalesce(d.source_name, '')
        group by
          d.source_name,
          d.source_kind,
          latest_runs.source_tier,
          latest_runs.finished_at,
          latest_runs.status,
          latest_runs.error_message
        order by
          max(d.last_seen_at) desc nulls last,
          count(*) desc,
          d.source_name
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement).mappings().all()

    return [
        SourceHealthItem(
            source_name=row["source_name"],
            source_kind=row["source_kind"],
            source_tier=row["source_tier"],
            document_count=int(row["document_count"]),
            latest_published_at=row["latest_published_at"],
            latest_seen_at=row["latest_seen_at"],
            latest_run_at=row["latest_run_at"],
            latest_run_status=row["latest_run_status"],
            latest_run_error=row["latest_run_error"],
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


def fetch_documents_for_event_detection(
    *,
    limit: int = 500,
    source_name: Optional[str] = None,
) -> list[TransactionDetectionDocument]:
    if limit < 1:
        return []

    conditions = []
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
              row_number() over (
                partition by y.iso_code
                order by
                  (
                    y.nuclear_generation_twh is not null
                    or y.nuclear_capacity_gw is not null
                    or y.nuclear_share_electricity_percent is not null
                  ) desc,
                  y.year desc
              ) as rank
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
              row_number() over (
                partition by y.iso_code
                order by
                  (
                    y.nuclear_generation_twh is not null
                    or y.nuclear_capacity_gw is not null
                    or y.nuclear_share_electricity_percent is not null
                  ) desc,
                  y.year desc
              ) as rank
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


def fetch_reactor_technology_summaries(iso_code: str | None = None) -> list[ReactorTechnologySummary]:
    params = {}
    country_filter = ""
    if iso_code:
        params["iso_code"] = iso_code.strip().upper()
        country_filter = "where c.iso3 = :iso_code"

    statement = sql_text(
        f"""
        select
          c.iso3 as iso_code,
          c.name as country_name,
          p.name as plant_name,
          r.name as reactor_name,
          r.status::text as reactor_status,
          rt.code as technology_code,
          rt.name as technology_name,
          r.net_capacity_mwe,
          coalesce(rs.title, ps.title) as source_title,
          coalesce(rs.url, ps.url) as source_url
        from public.reactors as r
        join public.power_plants as p
          on p.id = r.plant_id
        join public.countries as c
          on c.id = p.country_id
        left join public.reactor_technologies as rt
          on rt.id = r.technology_id
        left join public.source_documents as rs
          on rs.id = r.source_id
        left join public.source_documents as ps
          on ps.id = p.source_id
        {country_filter}
        order by c.name, p.name, r.name
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()

    return [
        ReactorTechnologySummary(
            iso_code=row["iso_code"],
            country_name=row["country_name"],
            plant_name=row["plant_name"],
            reactor_name=row["reactor_name"],
            reactor_status=row["reactor_status"],
            technology_code=row["technology_code"],
            technology_name=row["technology_name"],
            net_capacity_mwe=row["net_capacity_mwe"],
            source_title=row["source_title"],
            source_url=row["source_url"],
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


def fetch_event_metrics() -> EventMetrics:
    statement = sql_text(
        """
        select
          count(*) as event_count,
          count(*) filter (
            where source_tier in ('tier_1_official_structured', 'tier_2_official_document')
          ) as official_event_count,
          count(*) filter (where review_status = 'unreviewed') as needs_review_count,
          count(*) filter (where review_status = 'important') as important_count,
          count(*) filter (where review_status = 'duplicate') as duplicate_count,
          count(*) filter (where review_status = 'corrected') as corrected_count,
          max(event_date) as latest_event_date
        from public.nuclear_events
        """
    )

    with Session(get_engine()) as session:
        row = session.execute(statement).mappings().one()

    return EventMetrics(
        event_count=int(row["event_count"]),
        official_event_count=int(row["official_event_count"]),
        needs_review_count=int(row["needs_review_count"]),
        important_count=int(row["important_count"]),
        duplicate_count=int(row["duplicate_count"]),
        corrected_count=int(row["corrected_count"]),
        latest_event_date=row["latest_event_date"],
    )


def fetch_recent_events(
    *,
    limit: int = 50,
    country_iso_code: Optional[str] = None,
    review_status: Optional[str] = None,
    official_only: bool = False,
    since: datetime | None = None,
    themes: Sequence[str] = (),
    materiality_flags: Sequence[str] = (),
    needs_review: bool = False,
) -> list[EventListItem]:
    if limit < 1:
        return []

    conditions = []
    params: dict[str, object] = {"limit": limit}
    if country_iso_code:
        conditions.append("e.country_iso_code = :country_iso_code")
        params["country_iso_code"] = country_iso_code.strip().upper()
    if review_status:
        conditions.append("e.review_status = :review_status")
        params["review_status"] = review_status
    if official_only:
        conditions.append("e.source_tier in ('tier_1_official_structured', 'tier_2_official_document')")
    if since:
        conditions.append("coalesce(e.event_date, e.first_seen_at, e.created_at) >= :since")
        params["since"] = since
    _add_json_array_overlap_condition(conditions, params, "e.themes", themes, "theme")
    _add_json_array_overlap_condition(conditions, params, "e.materiality_flags", materiality_flags, "flag")
    if needs_review:
        conditions.append(
            """
            (
              e.review_status = 'unreviewed'
            )
            """
        )

    statement = sql_text(
        f"""
        with evidence_counts as (
          select
            event_id,
            count(*) as evidence_count,
            min(source_name) as source_name,
            min(source_url) as source_url
          from public.event_evidence
          group by event_id
        )
        select
          e.id,
          e.event_date,
          e.event_type,
          e.event_status,
          e.review_status,
          e.source_tier,
          e.country_iso_code,
          e.country_name,
          e.project_name,
          e.title,
          e.summary,
          e.amount_text,
          e.materiality_flags,
          e.themes,
          e.source_confidence,
          coalesce(evidence_counts.evidence_count, 0) as evidence_count,
          evidence_counts.source_name,
          evidence_counts.source_url
        from public.nuclear_events as e
        left join evidence_counts
          on evidence_counts.event_id = e.id
        {_where_clause(conditions)}
        order by e.event_date desc nulls last, e.created_at desc
        limit :limit
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()

    return [
        EventListItem(
            id=str(row["id"]),
            event_date=row["event_date"],
            event_type=row["event_type"],
            event_status=row["event_status"],
            review_status=row["review_status"],
            source_tier=row["source_tier"],
            country_iso_code=row["country_iso_code"],
            country_name=row["country_name"],
            project_name=row["project_name"],
            title=row["title"],
            summary=row["summary"],
            amount_text=row["amount_text"],
            materiality_flags=_json_text_list(row["materiality_flags"]),
            themes=_json_text_list(row["themes"]),
            source_confidence=float(row["source_confidence"]),
            evidence_count=int(row["evidence_count"]),
            source_name=row["source_name"],
            source_url=row["source_url"],
        )
        for row in rows
    ]


def fetch_daily_tape_events(limit: int = 25) -> list[EventListItem]:
    return fetch_recent_events(limit=limit, official_only=True)


def fetch_watchlist_events(
    *,
    limit: int = 50,
    since: datetime | None = None,
    entities: Sequence[str] = (),
    projects: Sequence[str] = (),
    countries: Sequence[str] = (),
    themes: Sequence[str] = (),
) -> list[EventListItem]:
    if limit < 1:
        return []

    conditions = []
    params: dict[str, object] = {"limit": limit}
    if since:
        conditions.append("coalesce(e.event_date, e.first_seen_at, e.created_at) >= :since")
        params["since"] = since

    watchlist_conditions = []
    if countries:
        names = []
        for index, country in enumerate(countries):
            key = f"watch_country_{index}"
            params[key] = country.strip().upper()
            names.append(f":{key}")
        if names:
            watchlist_conditions.append(f"e.country_iso_code in ({', '.join(names)})")

    theme_conditions = _json_array_overlap_sql("e.themes", themes, "watch_theme", params)
    if theme_conditions:
        watchlist_conditions.append(theme_conditions)

    if projects:
        project_names = []
        for index, project in enumerate(projects):
            key = f"watch_project_{index}"
            params[key] = project.strip().lower()
            project_names.append(f":{key}")
        if project_names:
            watchlist_conditions.append(
                f"""
                (
                  lower(coalesce(e.project_name, '')) in ({', '.join(project_names)})
                  or exists (
                    select 1
                    from public.event_projects ep
                    join public.projects p
                      on p.id = ep.project_id
                    left join public.project_aliases pa
                      on pa.project_id = p.id
                    where ep.event_id = e.id
                      and lower(coalesce(pa.alias, p.canonical_name)) in ({', '.join(project_names)})
                  )
                )
                """
            )

    if entities:
        entity_names = []
        for index, entity in enumerate(entities):
            key = f"watch_entity_{index}"
            params[key] = entity.strip().lower()
            entity_names.append(f":{key}")
        if entity_names:
            watchlist_conditions.append(
                f"""
                exists (
                  select 1
                  from public.event_entities ee
                  join public.entities en
                    on en.id = ee.entity_id
                  left join public.entity_aliases ea
                    on ea.entity_id = en.id
                  where ee.event_id = e.id
                    and lower(coalesce(ea.alias, en.canonical_name)) in ({', '.join(entity_names)})
                )
                """
            )

    if not watchlist_conditions:
        return []
    conditions.append(f"({' or '.join(watchlist_conditions)})")
    statement = _event_list_statement(conditions=conditions)
    with Session(get_engine()) as session:
        rows = session.execute(statement, params).mappings().all()
    return _event_list_items(rows)


def fetch_entity_summaries(limit: int = 100) -> list[EntitySummary]:
    if limit < 1:
        return []
    statement = sql_text(
        """
        select
          entities.id,
          entities.canonical_name,
          entities.entity_type,
          entities.country_iso_code,
          count(distinct event_entities.event_id) as event_count,
          max(nuclear_events.event_date) as latest_event_date,
          coalesce(jsonb_agg(distinct event_entities.role) filter (where event_entities.role is not null), '[]'::jsonb) as roles
        from public.entities
        join public.event_entities
          on event_entities.entity_id = entities.id
        join public.nuclear_events
          on nuclear_events.id = event_entities.event_id
        group by entities.id, entities.canonical_name, entities.entity_type, entities.country_iso_code
        order by event_count desc, latest_event_date desc nulls last, entities.canonical_name
        limit :limit
        """
    )
    with Session(get_engine()) as session:
        rows = session.execute(statement, {"limit": limit}).mappings().all()
    return [
        EntitySummary(
            id=str(row["id"]),
            canonical_name=row["canonical_name"],
            entity_type=row["entity_type"],
            country_iso_code=row["country_iso_code"],
            event_count=int(row["event_count"]),
            latest_event_date=row["latest_event_date"],
            roles=_json_text_list(row["roles"]),
        )
        for row in rows
    ]


def fetch_project_summaries(limit: int = 100) -> list[ProjectSummary]:
    if limit < 1:
        return []
    statement = sql_text(
        """
        select
          projects.id,
          projects.canonical_name,
          projects.project_type,
          projects.country_iso_code,
          projects.country_name,
          count(distinct event_projects.event_id) as event_count,
          max(nuclear_events.event_date) as latest_event_date,
          coalesce(jsonb_agg(distinct nuclear_events.event_type) filter (where nuclear_events.event_type is not null), '[]'::jsonb) as event_types
        from public.projects
        join public.event_projects
          on event_projects.project_id = projects.id
        join public.nuclear_events
          on nuclear_events.id = event_projects.event_id
        group by projects.id, projects.canonical_name, projects.project_type, projects.country_iso_code, projects.country_name
        order by event_count desc, latest_event_date desc nulls last, projects.canonical_name
        limit :limit
        """
    )
    with Session(get_engine()) as session:
        rows = session.execute(statement, {"limit": limit}).mappings().all()
    return [
        ProjectSummary(
            id=str(row["id"]),
            canonical_name=row["canonical_name"],
            project_type=row["project_type"],
            country_iso_code=row["country_iso_code"],
            country_name=row["country_name"],
            event_count=int(row["event_count"]),
            latest_event_date=row["latest_event_date"],
            event_types=_json_text_list(row["event_types"]),
        )
        for row in rows
    ]


def fetch_events_for_entity(entity_id: str, *, limit: int = 50) -> list[EventListItem]:
    if limit < 1:
        return []
    statement = _event_list_statement(
        relation_join="""
        join public.event_entities as relation
          on relation.event_id = e.id
        """,
        conditions=["relation.entity_id = cast(:entity_id as uuid)"],
    )
    with Session(get_engine()) as session:
        rows = session.execute(statement, {"entity_id": entity_id, "limit": limit}).mappings().all()
    return _event_list_items(rows)


def fetch_events_for_project(project_id: str, *, limit: int = 50) -> list[EventListItem]:
    if limit < 1:
        return []
    statement = _event_list_statement(
        relation_join="""
        join public.event_projects as relation
          on relation.event_id = e.id
        """,
        conditions=["relation.project_id = cast(:project_id as uuid)"],
    )
    with Session(get_engine()) as session:
        rows = session.execute(statement, {"project_id": project_id, "limit": limit}).mappings().all()
    return _event_list_items(rows)


def _event_list_statement(*, relation_join: str = "", conditions: Sequence[str] = ()):
    where_clause = _where_clause(conditions)
    return sql_text(
        f"""
        with evidence_counts as (
          select
            event_id,
            count(*) as evidence_count,
            min(source_name) as source_name,
            min(source_url) as source_url
          from public.event_evidence
          group by event_id
        )
        select
          e.id,
          e.event_date,
          e.event_type,
          e.event_status,
          e.review_status,
          e.source_tier,
          e.country_iso_code,
          e.country_name,
          e.project_name,
          e.title,
          e.summary,
          e.amount_text,
          e.materiality_flags,
          e.themes,
          e.source_confidence,
          coalesce(evidence_counts.evidence_count, 0) as evidence_count,
          evidence_counts.source_name,
          evidence_counts.source_url
        from public.nuclear_events as e
        {relation_join}
        left join evidence_counts
          on evidence_counts.event_id = e.id
        {where_clause}
        order by e.event_date desc nulls last, e.created_at desc
        limit :limit
        """
    )


def _event_list_items(rows) -> list[EventListItem]:
    return [
        EventListItem(
            id=str(row["id"]),
            event_date=row["event_date"],
            event_type=row["event_type"],
            event_status=row["event_status"],
            review_status=row["review_status"],
            source_tier=row["source_tier"],
            country_iso_code=row["country_iso_code"],
            country_name=row["country_name"],
            project_name=row["project_name"],
            title=row["title"],
            summary=row["summary"],
            amount_text=row["amount_text"],
            materiality_flags=_json_text_list(row["materiality_flags"]),
            themes=_json_text_list(row["themes"]),
            source_confidence=float(row["source_confidence"]),
            evidence_count=int(row["evidence_count"]),
            source_name=row["source_name"],
            source_url=row["source_url"],
        )
        for row in rows
    ]


REVIEW_STATUSES = {"reviewed", "important", "irrelevant", "duplicate", "corrected"}
EVENT_CORRECTION_FIELDS = {
    "event_type",
    "event_status",
    "event_date",
    "country_iso_code",
    "country_name",
    "project_name",
    "title",
    "summary",
    "amount_text",
    "materiality_flags",
    "themes",
}


def review_action_for_status(review_status: str, *, has_corrections: bool = False) -> str:
    if has_corrections or review_status == "corrected":
        return "correction"
    if review_status == "important":
        return "mark_important"
    if review_status == "irrelevant":
        return "mark_irrelevant"
    if review_status == "duplicate":
        return "mark_duplicate"
    return "status_update"


def fetch_review_metrics() -> ReviewMetrics:
    statement = sql_text(
        """
        select
          count(*) filter (
            where review_status = 'unreviewed'
          ) as queue_count,
          count(*) filter (where review_status = 'important') as important_count,
          count(*) filter (where review_status = 'corrected') as corrected_count,
          count(*) filter (where review_status = 'duplicate') as duplicate_count,
          count(*) filter (where review_status = 'unreviewed' and source_confidence < 0.7) as low_confidence_count,
          count(*) filter (
            where review_status = 'unreviewed'
              and source_tier in ('tier_1_official_structured', 'tier_2_official_document')
          ) as official_unreviewed_count
        from public.nuclear_events
        """
    )
    with Session(get_engine()) as session:
        row = session.execute(statement).mappings().one()
    return ReviewMetrics(
        queue_count=int(row["queue_count"]),
        important_count=int(row["important_count"]),
        corrected_count=int(row["corrected_count"]),
        duplicate_count=int(row["duplicate_count"]),
        low_confidence_count=int(row["low_confidence_count"]),
        official_unreviewed_count=int(row["official_unreviewed_count"]),
    )


def fetch_review_queue(limit: int = 50) -> list[ReviewQueueItem]:
    if limit < 1:
        return []

    statement = sql_text(
        """
        with evidence_counts as (
          select
            event_id,
            count(*) as evidence_count,
            min(source_name) as source_name,
            min(source_url) as source_url
          from public.event_evidence
          group by event_id
        )
        select
          e.id,
          e.event_date,
          e.event_type,
          e.event_status,
          e.review_status,
          e.source_tier,
          e.country_iso_code,
          e.country_name,
          e.project_name,
          e.title,
          e.summary,
          e.amount_text,
          e.materiality_flags,
          e.themes,
          e.source_confidence,
          coalesce(evidence_counts.evidence_count, 0) as evidence_count,
          evidence_counts.source_name,
          evidence_counts.source_url,
          e.review_note,
          e.duplicate_of_event_id,
          (
            case when e.source_tier in ('tier_1_official_structured', 'tier_2_official_document') then 40 else 0 end
            + case when e.event_status = 'needs_review' then 30 else 0 end
            + case when e.source_confidence < 0.7 then 25 else 0 end
            + case when e.materiality_flags ? 'needs_review' then 20 else 0 end
            + case when e.materiality_flags ? 'large_public_value' then 15 else 0 end
            + case when e.materiality_flags ? 'fuel_cycle_relevance' then 12 else 0 end
            + case when e.materiality_flags ? 'project_stage_change' then 10 else 0 end
            + case when e.materiality_flags ? 'supply_risk' then 10 else 0 end
          ) as review_priority,
          jsonb_strip_nulls(jsonb_build_object(
            'official_source', case when e.source_tier in ('tier_1_official_structured', 'tier_2_official_document') then true end,
            'needs_review_status', case when e.event_status = 'needs_review' then true end,
            'low_confidence', case when e.source_confidence < 0.7 then true end,
            'needs_review_flag', case when e.materiality_flags ? 'needs_review' then true end,
            'large_public_value', case when e.materiality_flags ? 'large_public_value' then true end,
            'fuel_cycle_relevance', case when e.materiality_flags ? 'fuel_cycle_relevance' then true end,
            'project_stage_change', case when e.materiality_flags ? 'project_stage_change' then true end,
            'supply_risk', case when e.materiality_flags ? 'supply_risk' then true end
          )) as review_reason_object
        from public.nuclear_events as e
        left join evidence_counts
          on evidence_counts.event_id = e.id
        where e.review_status = 'unreviewed'
        order by
          review_priority desc,
          e.event_date desc nulls last,
          e.created_at desc
        limit :limit
        """
    )

    with Session(get_engine()) as session:
        rows = session.execute(statement, {"limit": limit}).mappings().all()

    return [
        ReviewQueueItem(
            id=str(row["id"]),
            event_date=row["event_date"],
            event_type=row["event_type"],
            event_status=row["event_status"],
            review_status=row["review_status"],
            source_tier=row["source_tier"],
            country_iso_code=row["country_iso_code"],
            country_name=row["country_name"],
            project_name=row["project_name"],
            title=row["title"],
            summary=row["summary"],
            amount_text=row["amount_text"],
            materiality_flags=_json_text_list(row["materiality_flags"]),
            themes=_json_text_list(row["themes"]),
            source_confidence=float(row["source_confidence"]),
            evidence_count=int(row["evidence_count"]),
            source_name=row["source_name"],
            source_url=row["source_url"],
            review_note=row["review_note"],
            duplicate_of_event_id=str(row["duplicate_of_event_id"]) if row["duplicate_of_event_id"] else None,
            review_priority=int(row["review_priority"]),
            review_reasons=[
                key
                for key, value in _json_object(row["review_reason_object"]).items()
                if value is True
            ],
        )
        for row in rows
    ]


def fetch_event_evidence(event_id: str, *, limit: int = 10) -> list[EventEvidenceItem]:
    if limit < 1:
        return []
    statement = sql_text(
        """
        select
          id,
          event_id,
          document_id,
          evidence_kind,
          source_name,
          source_url,
          source_tier,
          published_at,
          snippet
        from public.event_evidence
        where event_id = cast(:event_id as uuid)
        order by
          case when source_tier in ('tier_1_official_structured', 'tier_2_official_document') then 0 else 1 end,
          published_at desc nulls last,
          created_at desc
        limit :limit
        """
    )
    with Session(get_engine()) as session:
        rows = session.execute(statement, {"event_id": event_id, "limit": limit}).mappings().all()
    return [
        EventEvidenceItem(
            id=str(row["id"]),
            event_id=str(row["event_id"]),
            document_id=str(row["document_id"]) if row["document_id"] else None,
            evidence_kind=row["evidence_kind"],
            source_name=row["source_name"],
            source_url=row["source_url"],
            source_tier=row["source_tier"],
            published_at=row["published_at"],
            snippet=row["snippet"],
        )
        for row in rows
    ]


def fetch_review_history(event_id: str, *, limit: int = 10) -> list[ReviewHistoryItem]:
    if limit < 1:
        return []
    statement = sql_text(
        """
        select
          id,
          event_id,
          review_status,
          previous_status,
          review_action,
          duplicate_of_event_id,
          patch_payload,
          note,
          reviewer,
          created_at
        from public.event_reviews
        where event_id = cast(:event_id as uuid)
        order by created_at desc
        limit :limit
        """
    )
    with Session(get_engine()) as session:
        rows = session.execute(statement, {"event_id": event_id, "limit": limit}).mappings().all()
    return [
        ReviewHistoryItem(
            id=str(row["id"]),
            event_id=str(row["event_id"]),
            review_status=row["review_status"],
            previous_status=row["previous_status"],
            review_action=row["review_action"],
            duplicate_of_event_id=str(row["duplicate_of_event_id"]) if row["duplicate_of_event_id"] else None,
            patch_payload=_json_object(row["patch_payload"]),
            note=row["note"],
            reviewer=row["reviewer"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def update_event_review(
    event_id: str,
    *,
    review_status: str,
    note: str | None = None,
    reviewer: str | None = None,
    duplicate_of_event_id: str | None = None,
    corrected_fields: dict[str, object] | None = None,
) -> None:
    if review_status not in REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {review_status}")

    now = datetime.now(timezone.utc)
    corrected_fields = {
        key: value
        for key, value in (corrected_fields or {}).items()
        if key in EVENT_CORRECTION_FIELDS and value not in (None, "", [])
    }
    if "country_iso_code" in corrected_fields and isinstance(corrected_fields["country_iso_code"], str):
        corrected_fields["country_iso_code"] = corrected_fields["country_iso_code"].strip().upper()
    for json_key in ("materiality_flags", "themes"):
        if json_key in corrected_fields:
            corrected_fields[json_key] = [
                str(value).strip()
                for value in corrected_fields[json_key]  # type: ignore[index]
                if str(value).strip()
            ]

    update_columns = [
        "review_status = :review_status",
        "review_note = :note",
        "reviewed_at = :reviewed_at",
        "duplicate_of_event_id = cast(:duplicate_of_event_id as uuid)",
        "updated_at = :updated_at",
    ]
    params: dict[str, object] = {
        "event_id": event_id,
        "review_status": review_status,
        "note": note,
        "reviewed_at": now,
        "duplicate_of_event_id": duplicate_of_event_id,
        "updated_at": now,
    }
    for field, value in corrected_fields.items():
        param_name = f"corrected_{field}"
        if field in {"materiality_flags", "themes"}:
            update_columns.append(f"{field} = cast(:{param_name} as jsonb)")
            params[param_name] = json.dumps(value)
        else:
            update_columns.append(f"{field} = :{param_name}")
            params[param_name] = value

    review_action = review_action_for_status(review_status, has_corrections=bool(corrected_fields))
    with Session(get_engine()) as session:
        prior = session.execute(
            sql_text(
                """
                select review_status
                from public.nuclear_events
                where id = cast(:event_id as uuid)
                """
            ),
            {"event_id": event_id},
        ).mappings().first()
        previous_status = prior["review_status"] if prior else None
        session.execute(
            sql_text(
                f"""
                update public.nuclear_events
                set {", ".join(update_columns)}
                where id = cast(:event_id as uuid)
                """
            ),
            params,
        )
        session.execute(
            sql_text(
                """
                insert into public.event_reviews (
                  event_id,
                  review_status,
                  previous_status,
                  review_action,
                  duplicate_of_event_id,
                  patch_payload,
                  note,
                  reviewer
                )
                values (
                  cast(:event_id as uuid),
                  :review_status,
                  :previous_status,
                  :review_action,
                  cast(:duplicate_of_event_id as uuid),
                  cast(:patch_payload as jsonb),
                  :note,
                  :reviewer
                )
                """
            ),
            {
                "event_id": event_id,
                "review_status": review_status,
                "previous_status": previous_status,
                "review_action": review_action,
                "duplicate_of_event_id": duplicate_of_event_id,
                "patch_payload": json.dumps(corrected_fields),
                "note": note,
                "reviewer": reviewer,
            },
        )
        session.commit()


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


def _add_json_array_overlap_condition(
    conditions: list[str],
    params: dict[str, object],
    column_sql: str,
    values: Sequence[str],
    prefix: str,
) -> None:
    condition = _json_array_overlap_sql(column_sql, values, prefix, params)
    if condition:
        conditions.append(condition)


def _json_array_overlap_sql(
    column_sql: str,
    values: Sequence[str],
    prefix: str,
    params: dict[str, object],
) -> str:
    cleaned_values = [value.strip() for value in values if value and value.strip()]
    if not cleaned_values:
        return ""
    comparisons = []
    for index, value in enumerate(cleaned_values):
        key = f"{prefix}_{index}"
        params[key] = value
        comparisons.append(f"item.value = :{key}")
    return (
        f"exists (select 1 from jsonb_array_elements_text({column_sql}) as item(value) "
        f"where {' or '.join(comparisons)})"
    )


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


def _json_text_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _json_object(value) -> dict:
    if not value:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return dict(value) if isinstance(value, dict) else {}


def _estimate_token_count(text: str) -> int:
    return max(1, len(text.split()))
