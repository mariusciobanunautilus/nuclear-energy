from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx

from nuclear_energy.models import OfficialTransactionRecord, RawDocument, SourceKind
from nuclear_energy.sources.official_common import (
    USER_AGENT,
    clean_string,
    coerce_float,
    compact_text,
    infer_location,
    money_text,
    parse_date,
    truncate_text,
)


USASPENDING_AWARD_SEARCH_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
USASPENDING_AWARD_URL = "https://www.usaspending.gov/award/{generated_internal_id}"
DEFAULT_USASPENDING_TERMS = (
    "nuclear power",
    "nuclear reactor",
    "small modular reactor",
    "microreactor",
    "uranium",
    "HALEU",
    "nuclear fuel",
    "reactor fuel",
)
CONTRACT_AWARD_TYPE_CODES = ("A", "B", "C", "D")
USASPENDING_FIELDS = (
    "Award ID",
    "Recipient Name",
    "Base Obligation Date",
    "Last Modified Date",
    "Start Date",
    "End Date",
    "Award Amount",
    "Description",
    "Awarding Agency",
    "Awarding Sub Agency",
    "Funding Agency",
    "Funding Sub Agency",
    "Place of Performance Country Code",
    "Place of Performance State Code",
    "Contract Award Type",
    "naics_description",
    "psc_description",
)
VISIBLE_NUCLEAR_TERMS = (
    "advanced reactor",
    "enrichment",
    "haleu",
    "microreactor",
    "nuclear",
    "reactor",
    "uranium",
)


def fetch_usaspending_nuclear_awards(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    lookback_days: int = 730,
    limit: int = 50,
    terms: tuple[str, ...] = DEFAULT_USASPENDING_TERMS,
    timeout: float = 30.0,
) -> list[OfficialTransactionRecord]:
    if limit < 1:
        return []

    terms = terms or DEFAULT_USASPENDING_TERMS
    today = date.today()
    end_date = end_date or today
    start_date = start_date or end_date - timedelta(days=lookback_days)

    records: list[OfficialTransactionRecord] = []
    seen_ids: set[str] = set()
    for term in terms:
        if len(records) >= limit:
            break
        payload = _award_search_payload(
            term=term,
            start_date=start_date,
            end_date=end_date,
            limit=min(100, max(1, limit - len(records))),
        )
        response = httpx.post(
            USASPENDING_AWARD_SEARCH_URL,
            json=payload,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        response.raise_for_status()
        for result in response.json().get("results", []):
            record_id = _record_id(result)
            if not record_id or record_id in seen_ids:
                continue
            record = _result_to_record(result, query_term=term)
            if record:
                records.append(record)
                seen_ids.add(record_id)
            if len(records) >= limit:
                break

    return records


def _award_search_payload(*, term: str, start_date: date, end_date: date, limit: int) -> dict[str, Any]:
    return {
        "filters": {
            "keywords": [term],
            "award_type_codes": list(CONTRACT_AWARD_TYPE_CODES),
            "time_period": [
                {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                }
            ],
        },
        "fields": list(USASPENDING_FIELDS),
        "page": 1,
        "limit": limit,
        "sort": "Base Obligation Date",
        "order": "desc",
        "subawards": False,
    }


def _result_to_record(result: dict[str, Any], *, query_term: str) -> OfficialTransactionRecord | None:
    description = clean_string(result.get("Description")) or ""
    recipient = clean_string(result.get("Recipient Name"))
    awarding_agency = clean_string(result.get("Awarding Agency"))
    awarding_sub_agency = clean_string(result.get("Awarding Sub Agency"))
    award_id = clean_string(result.get("Award ID"))
    generated_id = clean_string(result.get("generated_internal_id"))
    record_id = _record_id(result)
    if not record_id or not award_id:
        return None

    evidence_text = compact_text(
        description,
        recipient,
        awarding_agency,
        awarding_sub_agency,
        result.get("naics_description"),
        result.get("psc_description"),
    )
    if not _is_visible_nuclear_record(evidence_text):
        return None

    url = USASPENDING_AWARD_URL.format(generated_internal_id=generated_id or award_id)
    transaction_date = parse_date(result.get("Base Obligation Date")) or parse_date(result.get("Start Date"))
    amount = coerce_float(result.get("Award Amount"))
    amount_label = money_text(amount, "USD")
    country_iso_code, country_name, plant_name = infer_location(evidence_text, default_iso_code="USA")
    transaction_type = _transaction_type(evidence_text)
    counterparties = list(dict.fromkeys(value for value in (recipient, awarding_agency, awarding_sub_agency) if value))

    title = _title(
        award_id=award_id,
        recipient=recipient,
        agency=awarding_agency,
        description=description,
    )
    summary = _summary(
        agency=awarding_agency,
        recipient=recipient,
        amount_text=amount_label,
        description=description,
    )

    raw_payload = {**result, "query_term": query_term}
    document = RawDocument(
        source_kind=SourceKind.usaspending,
        source_name="USAspending.gov",
        external_id=record_id,
        title=title,
        url=url,
        published_at=transaction_date,
        summary=summary,
        content=_document_content(result, query_term=query_term),
        authors=[value for value in (awarding_agency, awarding_sub_agency) if value],
        tags=[tag for tag in ("official_award", transaction_type, query_term) if tag],
        raw_payload=raw_payload,
    )

    return OfficialTransactionRecord(
        document=document,
        transaction_external_id=f"usaspending-{record_id}",
        transaction_date=transaction_date,
        country_iso_code=country_iso_code,
        country_name=country_name,
        plant_name=plant_name,
        project_name=plant_name,
        transaction_type=transaction_type,
        stage="confirmed_award",
        title=title,
        summary=summary,
        source_name="USAspending.gov",
        source_url=url,
        amount_text=amount_label,
        amount=amount,
        currency="USD" if amount is not None else None,
        counterparties=counterparties,
        matched_terms=_matched_visible_terms(evidence_text),
        confidence=0.95 if amount is not None else 0.85,
        raw_payload=raw_payload,
    )


def _record_id(result: dict[str, Any]) -> str | None:
    return clean_string(result.get("generated_internal_id")) or clean_string(result.get("Award ID"))


def _is_visible_nuclear_record(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in VISIBLE_NUCLEAR_TERMS)


def _matched_visible_terms(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in VISIBLE_NUCLEAR_TERMS if term in lowered]


def _transaction_type(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ("fuel", "haleu", "uranium", "enrichment")):
        return "fuel_supply"
    if any(term in lowered for term in ("construction", "refurbishment", "maintenance", "engineering")):
        return "construction_refurbishment"
    if any(term in lowered for term in ("grant", "funding", "financing", "investment")):
        return "financing"
    return "contract_award"


def _title(*, award_id: str, recipient: str | None, agency: str | None, description: str) -> str:
    actor = recipient or agency or "recipient"
    preview = truncate_text(description or "nuclear-related public award", 120)
    return f"USAspending award {award_id} to {actor}: {preview}"


def _summary(
    *,
    agency: str | None,
    recipient: str | None,
    amount_text: str | None,
    description: str,
) -> str:
    amount_part = f" for {amount_text}" if amount_text else ""
    agency_part = f"{agency} awarded" if agency else "US public award"
    recipient_part = f" to {recipient}" if recipient else ""
    description_part = truncate_text(description or "nuclear-related work", 180)
    return f"{agency_part}{recipient_part}{amount_part}: {description_part}"


def _document_content(result: dict[str, Any], *, query_term: str) -> str:
    lines = [
        f"Query term: {query_term}",
        f"Award ID: {clean_string(result.get('Award ID')) or ''}",
        f"Recipient: {clean_string(result.get('Recipient Name')) or ''}",
        f"Awarding agency: {clean_string(result.get('Awarding Agency')) or ''}",
        f"Awarding sub-agency: {clean_string(result.get('Awarding Sub Agency')) or ''}",
        f"Funding agency: {clean_string(result.get('Funding Agency')) or ''}",
        f"Funding sub-agency: {clean_string(result.get('Funding Sub Agency')) or ''}",
        f"Base obligation date: {clean_string(result.get('Base Obligation Date')) or ''}",
        f"Start date: {clean_string(result.get('Start Date')) or ''}",
        f"End date: {clean_string(result.get('End Date')) or ''}",
        f"Award amount: {money_text(coerce_float(result.get('Award Amount')), 'USD') or ''}",
        f"Award type: {clean_string(result.get('Contract Award Type')) or ''}",
        f"NAICS: {clean_string(result.get('naics_description')) or ''}",
        f"PSC: {clean_string(result.get('psc_description')) or ''}",
        f"Description: {clean_string(result.get('Description')) or ''}",
    ]
    return "\n".join(lines)
