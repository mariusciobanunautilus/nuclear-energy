from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl


class SourceKind(str, Enum):
    rss = "rss"
    gdelt = "gdelt"
    eur_lex = "eur_lex"
    congress = "congress"
    federal_register = "federal_register"
    regulations_gov = "regulations_gov"
    usaspending = "usaspending"
    eu_ted = "eu_ted"
    sec_edgar = "sec_edgar"
    iaea_pris = "iaea_pris"
    eia = "eia"
    entsoe = "entsoe"


class RawDocument(BaseModel):
    source_kind: SourceKind
    source_name: str
    external_id: str
    title: str
    url: HttpUrl
    published_at: Optional[datetime] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def url_text(self) -> str:
        return str(self.url)


class CountryEnergyYear(BaseModel):
    iso_code: str = Field(min_length=3, max_length=3)
    country_name: str = Field(min_length=1)
    year: int = Field(ge=1950, le=2100)
    nuclear_generation_twh: Optional[float] = None
    nuclear_share_electricity_percent: Optional[float] = None
    nuclear_capacity_gw: Optional[float] = None
    electricity_generation_twh: Optional[float] = None
    electricity_demand_twh: Optional[float] = None
    net_electricity_imports_twh: Optional[float] = None
    fossil_generation_twh: Optional[float] = None
    renewables_generation_twh: Optional[float] = None
    clean_generation_twh: Optional[float] = None
    source_name: str = "Ember Yearly Electricity Data"
    source_url: str = "https://files.ember-energy.org/public-downloads/generation/outputs/release_generation_yearly_global.csv"
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class LiveGenerationSnapshot(BaseModel):
    observed_at: datetime
    country_iso_code: str = Field(min_length=3, max_length=3)
    country_name: str = Field(min_length=1)
    demand_mw: Optional[int] = None
    production_mw: Optional[int] = None
    net_import_export_mw: Optional[int] = None
    nuclear_mw: Optional[int] = None
    wind_mw: Optional[int] = None
    hydro_mw: Optional[int] = None
    hydrocarbons_mw: Optional[int] = None
    coal_mw: Optional[int] = None
    solar_mw: Optional[int] = None
    biomass_mw: Optional[int] = None
    storage_mw: Optional[int] = None
    source_name: str = "Transelectrica Live SEN"
    source_url: str = "https://www.sistemulenergetic.ro/"
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class NuclearTransaction(BaseModel):
    external_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    transaction_date: Optional[datetime] = None
    country_iso_code: Optional[str] = Field(default=None, min_length=3, max_length=3)
    country_name: Optional[str] = None
    plant_name: Optional[str] = None
    project_name: Optional[str] = None
    transaction_type: str = Field(min_length=1)
    stage: str = "detected"
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    amount_text: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    counterparties: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class NuclearEvent(BaseModel):
    external_id: str = Field(min_length=1)
    source_document_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    event_status: str = "detected"
    source_tier: str = "unclassified"
    event_date: Optional[datetime] = None
    country_iso_code: Optional[str] = Field(default=None, min_length=3, max_length=3)
    country_name: Optional[str] = None
    project_name: Optional[str] = None
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    amount_text: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    materiality_flags: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    source_confidence: float = Field(ge=0, le=1)
    evidence_snippet: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class OfficialTransactionRecord(BaseModel):
    document: RawDocument
    transaction_external_id: str = Field(min_length=1)
    transaction_date: Optional[datetime] = None
    country_iso_code: Optional[str] = Field(default=None, min_length=3, max_length=3)
    country_name: Optional[str] = None
    plant_name: Optional[str] = None
    project_name: Optional[str] = None
    transaction_type: str = Field(min_length=1)
    stage: str
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    amount_text: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    counterparties: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def document_key(self) -> tuple[str, str]:
        return (self.document.source_kind.value, self.document.external_id)

    def to_transaction(self, document_id: str) -> NuclearTransaction:
        return NuclearTransaction(
            external_id=self.transaction_external_id,
            document_id=document_id,
            transaction_date=self.transaction_date,
            country_iso_code=self.country_iso_code,
            country_name=self.country_name,
            plant_name=self.plant_name,
            project_name=self.project_name,
            transaction_type=self.transaction_type,
            stage=self.stage,
            title=self.title,
            summary=self.summary,
            source_name=self.source_name,
            source_url=self.source_url,
            amount_text=self.amount_text,
            amount=self.amount,
            currency=self.currency,
            counterparties=self.counterparties,
            matched_terms=self.matched_terms,
            confidence=self.confidence,
            raw_payload=self.raw_payload,
        )
