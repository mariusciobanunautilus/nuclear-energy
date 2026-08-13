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
