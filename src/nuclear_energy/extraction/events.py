from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from nuclear_energy.db import source_tier_for_kind
from nuclear_energy.extraction.resolution import match_entity_mentions
from nuclear_energy.extraction.transactions import (
    _country_for_iso_code,
    _document_text,
    _extract_money,
    _match_countries,
    _match_plants,
    _matched_terms,
    _normalise_text,
)
from nuclear_energy.models import NuclearEvent


class EventDocument(Protocol):
    id: str
    title: str
    url: str
    source_name: str
    source_kind: str
    published_at: datetime | None
    summary: str | None
    content: str | None


@dataclass(frozen=True)
class EventTermGroup:
    event_type: str
    terms: tuple[str, ...]
    themes: tuple[str, ...]
    default_status: str = "detected"


EVENT_TERM_GROUPS = (
    EventTermGroup(
        "license_approval",
        (
            "license approval",
            "licence approval",
            "approved the license",
            "approved the licence",
            "regulatory approval",
            "construction permit approved",
            "operating license approved",
            "operating licence approved",
            "authorization",
            "authorisation",
        ),
        ("regulation", "project_stage"),
        "confirmed",
    ),
    EventTermGroup(
        "license_application",
        (
            "license application",
            "licence application",
            "applied for a license",
            "applied for a licence",
            "permit application",
            "construction permit application",
            "combined license application",
            "environmental permit",
        ),
        ("regulation", "project_stage"),
        "proposed",
    ),
    EventTermGroup(
        "policy_change",
        (
            "nuclear policy",
            "energy policy",
            "nuclear strategy",
            "nuclear roadmap",
            "legislation",
            "bill",
            "law",
            "state aid",
            "subsidy",
            "tax credit",
            "government support",
        ),
        ("policy",),
        "confirmed",
    ),
    EventTermGroup(
        "construction_start",
        (
            "construction started",
            "began construction",
            "begins construction",
            "breaks ground",
            "groundbreaking",
            "first concrete",
            "site preparation",
        ),
        ("construction", "project_stage"),
        "confirmed",
    ),
    EventTermGroup(
        "contract_award",
        (
            "signed a contract",
            "signs a contract",
            "contracted for",
            "contracted to supply",
            "supply contract",
            "supply of key equipment",
            "key equipment",
            "component supply",
            "service agreement",
            "memorandum of understanding",
        ),
        ("procurement", "project_stage"),
        "reported",
    ),
    EventTermGroup(
        "reported_development",
        (
            "installed",
            "module installed",
            "installation completed",
            "hot tests completed",
            "cold tests completed",
            "first criticality",
            "grid connection",
            "connected to the grid",
            "fuel loaded",
            "loading of fuel",
            "fuel loading",
            "began loading fuel",
        ),
        ("construction", "operations", "project_stage"),
        "reported",
    ),
    EventTermGroup(
        "construction_refurbishment",
        (
            "life extension",
            "lifetime extension",
            "refurbishment",
            "modernization",
            "modernisation",
            "uprate",
            "maintenance outage",
            "service agreement",
        ),
        ("construction", "operations"),
        "reported",
    ),
    EventTermGroup(
        "restart",
        (
            "restart",
            "restarts",
            "restarted",
            "returns to service",
            "returned to service",
            "reopen",
            "reactivation",
        ),
        ("operations", "project_stage"),
        "reported",
    ),
    EventTermGroup(
        "outage",
        (
            "unplanned outage",
            "forced outage",
            "offline",
            "shut down",
            "shutdown",
            "automatic trip",
            "reactor trip",
            "maintenance outage",
            "taken offline",
            "taken off line",
            "disconnected from the grid",
            "disconnected from the national power grid",
            "controlled shutdown",
            "shutting down",
        ),
        ("operations", "supply_risk"),
        "reported",
    ),
    EventTermGroup(
        "delay_or_cost_overrun",
        (
            "delay",
            "delayed",
            "postponed",
            "cost overrun",
            "budget increase",
            "cost increase",
            "behind schedule",
            "schedule slippage",
        ),
        ("project_risk",),
        "reported",
    ),
    EventTermGroup(
        "fuel_supply",
        (
            "uranium supply",
            "uranium",
            "enrichment",
            "haleu",
            "conversion",
            "fuel fabrication",
            "nuclear fuel",
            "fuel supply",
            "offtake",
        ),
        ("fuel_cycle",),
        "reported",
    ),
    EventTermGroup(
        "sanction_or_export_control",
        (
            "sanction",
            "sanctions",
            "export control",
            "export ban",
            "import ban",
            "restriction",
            "restricted exports",
            "supply restriction",
        ),
        ("policy", "supply_risk"),
        "confirmed",
    ),
)


def detect_nuclear_events(
    documents: list[EventDocument],
    *,
    min_confidence: float = 0.5,
) -> list[NuclearEvent]:
    events = []
    for document in documents:
        event = _detect_document_event(document)
        if event and event.source_confidence >= min_confidence:
            events.append(event)
    return events


def _detect_document_event(document: EventDocument) -> NuclearEvent | None:
    text = _document_text(document)
    normalised_text = _normalise_text(text)
    matched_entities = match_entity_mentions(text)
    matched_by_type = {
        group.event_type: _matched_terms(normalised_text, group.terms)
        for group in EVENT_TERM_GROUPS
    }
    matched_by_type = {event_type: terms for event_type, terms in matched_by_type.items() if terms}
    if not matched_by_type:
        return None

    plants = _match_plants(normalised_text)
    countries = _match_countries(normalised_text)
    for plant in plants:
        if plant.iso_code not in {country.iso_code for country in countries}:
            country = _country_for_iso_code(plant.iso_code)
            if country:
                countries.append(country)
    if not countries and not plants:
        return None

    group = _best_event_group(matched_by_type)
    matched_terms = matched_by_type[group.event_type]
    amount_text, amount, currency = _extract_money(text)
    plant = plants[0] if plants else None
    country = _primary_event_country(normalised_text, countries, plant)
    source_tier = source_tier_for_kind(document.source_kind, document.source_name)
    event_status = _event_status(group.default_status, source_tier)
    materiality_flags = _materiality_flags(
        event_type=group.event_type,
        event_status=event_status,
        source_tier=source_tier,
        amount=amount,
        has_plant=plant is not None,
    )
    confidence = _confidence_score(
        matched_terms=matched_terms,
        source_tier=source_tier,
        has_country=country is not None,
        has_plant=plant is not None,
    )

    return NuclearEvent(
        external_id=_external_id(
            document_id=document.id,
            event_type=group.event_type,
            country_iso_code=country.iso_code if country else None,
            project_name=plant.plant_name if plant else None,
            matched_terms=matched_terms,
        ),
        source_document_id=document.id,
        event_type=group.event_type,
        event_status=event_status,
        source_tier=source_tier,
        event_date=document.published_at,
        country_iso_code=country.iso_code if country else None,
        country_name=country.country_name if country else None,
        project_name=plant.plant_name if plant else None,
        title=document.title.strip(),
        summary=_summary(
            event_type=group.event_type,
            country_name=country.country_name if country else None,
            project_name=plant.plant_name if plant else None,
            title=document.title,
        ),
        amount_text=amount_text,
        amount=amount,
        currency=currency,
        materiality_flags=materiality_flags,
        themes=list(dict.fromkeys(group.themes)),
        source_confidence=confidence,
        evidence_snippet=_evidence_snippet(text, matched_terms),
        source_name=document.source_name,
        source_url=document.url,
        raw_payload={
            "source_kind": document.source_kind,
            "matched_terms": matched_terms,
            "matched_entities": matched_entities,
            "matched_country_aliases": [country.iso_code for country in countries],
            "matched_plant_aliases": [plant.plant_name for plant in plants],
        },
    )


def _best_event_group(matched_by_type: dict[str, list[str]]) -> EventTermGroup:
    event_type = max(
        matched_by_type,
        key=lambda value: (len(matched_by_type[value]), _event_type_priority(value)),
    )
    return next(group for group in EVENT_TERM_GROUPS if group.event_type == event_type)


def _event_type_priority(event_type: str) -> int:
    priorities = {
        "license_approval": 12,
        "construction_start": 11,
        "reported_development": 10,
        "sanction_or_export_control": 10,
        "delay_or_cost_overrun": 9,
        "license_application": 8,
        "restart": 7,
        "contract_award": 6,
        "outage": 6,
        "policy_change": 5,
        "construction_refurbishment": 4,
        "fuel_supply": 3,
    }
    return priorities.get(event_type, 0)


def _event_status(default_status: str, source_tier: str) -> str:
    if source_tier in {"tier_1_official_structured", "tier_2_official_document"}:
        return default_status if default_status in {"confirmed", "proposed"} else "confirmed"
    if source_tier == "tier_5_discovery_feed":
        return "detected"
    return default_status


def _primary_event_country(normalised_text: str, countries, plant):
    if plant:
        plant_country = _country_for_iso_code(plant.iso_code)
        if plant_country:
            return plant_country
    if not countries:
        return None
    return max(countries, key=lambda country: _country_mention_position(normalised_text, country))


def _country_mention_position(normalised_text: str, country) -> int:
    positions = []
    for alias in country.aliases:
        term = _normalise_text(alias).strip()
        matches = list(re.finditer(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalised_text))
        if matches:
            positions.append(matches[-1].start())
    return max(positions) if positions else -1


def _materiality_flags(
    *,
    event_type: str,
    event_status: str,
    source_tier: str,
    amount: float | None,
    has_plant: bool,
) -> list[str]:
    flags = []
    if source_tier in {"tier_1_official_structured", "tier_2_official_document"}:
        flags.append("official_confirmation")
    if amount is not None and amount >= 50_000_000:
        flags.append("large_public_value")
    if amount is not None:
        flags.append("public_amount")
    if event_type in {"fuel_supply", "sanction_or_export_control"}:
        flags.append("fuel_cycle_relevance")
    if event_type in {"license_application", "license_approval", "construction_start", "restart"}:
        flags.append("project_stage_change")
    if event_type in {"delay_or_cost_overrun", "outage", "sanction_or_export_control"}:
        flags.append("supply_risk")
    if event_type == "policy_change":
        flags.append("country_policy_shift")
    if has_plant:
        flags.append("project_specific")
    if event_status in {"detected", "needs_review"}:
        flags.append("needs_review")
    return list(dict.fromkeys(flags))


def _confidence_score(
    *,
    matched_terms: list[str],
    source_tier: str,
    has_country: bool,
    has_plant: bool,
) -> float:
    score = 0.35 + min(len(matched_terms), 4) * 0.08
    if source_tier == "tier_1_official_structured":
        score += 0.2
    elif source_tier == "tier_2_official_document":
        score += 0.16
    elif source_tier == "tier_4_reported_media":
        score += 0.08
    if has_country:
        score += 0.1
    if has_plant:
        score += 0.1
    return min(score, 0.96)


def _summary(*, event_type: str, country_name: str | None, project_name: str | None, title: str) -> str:
    location = project_name or country_name or "nuclear sector"
    return f"{event_type.replace('_', ' ').title()} event for {location}: {title.strip()}"


def _evidence_snippet(text: str, matched_terms: list[str], *, radius: int = 260) -> str:
    lowered = text.lower()
    positions = [lowered.find(term.lower()) for term in matched_terms]
    positions = [position for position in positions if position >= 0]
    if not positions:
        return text.strip()[: radius * 2]
    center = min(positions)
    start = max(0, center - radius)
    end = min(len(text), center + radius)
    return text[start:end].strip()


def _external_id(
    *,
    document_id: str,
    event_type: str,
    country_iso_code: str | None,
    project_name: str | None,
    matched_terms: list[str],
) -> str:
    signature = "|".join(
        [
            document_id,
            event_type,
            country_iso_code or "",
            project_name or "",
            ",".join(sorted(matched_terms)),
        ]
    )
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:24]
    return f"doc-event-{digest}"
