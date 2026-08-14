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


TED_NOTICE_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
DEFAULT_TED_TERMS = ("nuclear", "uranium", "reactor")
TED_FIELDS = (
    "publication-number",
    "publication-date",
    "notice-type",
    "buyer-name",
    "buyer-country",
    "winner-name",
    "total-value",
    "total-value-cur",
    "classification-cpv",
)
TED_COUNTRY_NAMES = {
    "AUT": "Austria",
    "BEL": "Belgium",
    "BGR": "Bulgaria",
    "CHE": "Switzerland",
    "CYP": "Cyprus",
    "CZE": "Czechia",
    "DEU": "Germany",
    "DNK": "Denmark",
    "ESP": "Spain",
    "EST": "Estonia",
    "FIN": "Finland",
    "FRA": "France",
    "GBR": "United Kingdom",
    "GRC": "Greece",
    "HRV": "Croatia",
    "HUN": "Hungary",
    "IRL": "Ireland",
    "ITA": "Italy",
    "LTU": "Lithuania",
    "LUX": "Luxembourg",
    "LVA": "Latvia",
    "MLT": "Malta",
    "NLD": "Netherlands",
    "NOR": "Norway",
    "POL": "Poland",
    "PRT": "Portugal",
    "ROU": "Romania",
    "SVK": "Slovakia",
    "SVN": "Slovenia",
    "SWE": "Sweden",
}
NUCLEAR_CPV_PREFIXES = ("09344", "14733")


def fetch_ted_nuclear_procurements(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    lookback_days: int = 730,
    limit: int = 50,
    terms: tuple[str, ...] = DEFAULT_TED_TERMS,
    timeout: float = 30.0,
) -> list[OfficialTransactionRecord]:
    if limit < 1:
        return []

    terms = terms or DEFAULT_TED_TERMS
    today = date.today()
    end_date = end_date or today
    start_date = start_date or end_date - timedelta(days=lookback_days)

    payload = {
        "query": _expert_query(terms=terms, start_date=start_date, end_date=end_date),
        "fields": list(TED_FIELDS),
        "page": 1,
        "limit": min(limit, 100),
        "paginationMode": "PAGE_NUMBER",
        "scope": "ALL",
        "onlyLatestVersions": True,
    }
    response = httpx.post(
        TED_NOTICE_SEARCH_URL,
        json=payload,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()

    records = []
    for notice in response.json().get("notices", []):
        record = _notice_to_record(notice)
        if record:
            records.append(record)
        if len(records) >= limit:
            break
    return records


def _expert_query(*, terms: tuple[str, ...], start_date: date, end_date: date) -> str:
    term_query = " OR ".join(f"FT ~ {term}" for term in terms)
    return f"({term_query}) AND publication-date>={start_date:%Y%m%d} AND publication-date<={end_date:%Y%m%d}"


def _notice_to_record(notice: dict[str, Any]) -> OfficialTransactionRecord | None:
    publication_number = clean_string(notice.get("publication-number"))
    if not publication_number:
        return None

    url = _notice_url(notice)
    if not url:
        return None

    buyer = _multilingual_first(notice.get("buyer-name"))
    winners = _multilingual_list(notice.get("winner-name"))
    winner = winners[0] if winners else None
    buyer_country = _first(notice.get("buyer-country"))
    country_iso_code = clean_string(buyer_country).upper() if buyer_country else None
    country_name = TED_COUNTRY_NAMES.get(country_iso_code or "")
    notice_type = clean_string(notice.get("notice-type")) or "notice"
    publication_date = parse_date(notice.get("publication-date"))
    amount = coerce_float(_first(notice.get("total-value")) or notice.get("total-value"))
    currency = clean_string(_first(notice.get("total-value-cur"))) or ("EUR" if amount is not None else None)
    amount_label = money_text(amount, currency or "EUR")
    cpv_codes = [clean_string(value) for value in (notice.get("classification-cpv") or [])]
    cpv_codes = [value for value in cpv_codes if value]

    evidence_text = compact_text(
        publication_number,
        notice_type,
        buyer,
        winner,
        country_name,
        " ".join(cpv_codes),
    )
    inferred_iso, inferred_name, plant_name = infer_location(evidence_text, default_iso_code=country_iso_code)
    country_iso_code = inferred_iso or country_iso_code
    country_name = inferred_name or country_name
    if not country_iso_code:
        return None

    transaction_type = _transaction_type(cpv_codes, evidence_text)
    stage = "confirmed_award" if winner else "public_tender"
    counterparties = [party for party in (buyer, *winners) if party]
    title = _title(
        publication_number=publication_number,
        notice_type=notice_type,
        buyer=buyer,
        winner=winner,
    )
    summary = _summary(
        notice_type=notice_type,
        buyer=buyer,
        winner=winner,
        country_name=country_name,
        amount_text=amount_label,
    )
    raw_payload = notice

    document = RawDocument(
        source_kind=SourceKind.eu_ted,
        source_name="EU TED",
        external_id=publication_number,
        title=title,
        url=url,
        published_at=publication_date,
        summary=summary,
        content=_document_content(notice, url=url),
        authors=[buyer] if buyer else [],
        tags=[tag for tag in ("official_procurement", stage, transaction_type, notice_type) if tag],
        raw_payload=raw_payload,
    )

    return OfficialTransactionRecord(
        document=document,
        transaction_external_id=f"eu-ted-{publication_number}",
        transaction_date=publication_date,
        country_iso_code=country_iso_code,
        country_name=country_name,
        plant_name=plant_name,
        project_name=plant_name,
        transaction_type=transaction_type,
        stage=stage,
        title=title,
        summary=summary,
        source_name="EU TED",
        source_url=url,
        amount_text=amount_label,
        amount=amount,
        currency=currency,
        counterparties=counterparties,
        matched_terms=_matched_terms(cpv_codes, evidence_text),
        confidence=0.92 if stage == "confirmed_award" else 0.82,
        raw_payload=raw_payload,
    )


def _notice_url(notice: dict[str, Any]) -> str | None:
    links = notice.get("links") or {}
    for section, language in (("html", "ENG"), ("htmlDirect", "ENG"), ("pdf", "ENG")):
        url = clean_string((links.get(section) or {}).get(language))
        if url:
            return url
    for section in ("html", "htmlDirect", "pdf"):
        values = links.get(section) or {}
        if isinstance(values, dict):
            for value in values.values():
                url = clean_string(value)
                if url:
                    return url
    return None


def _multilingual_first(value: Any) -> str | None:
    values = _multilingual_list(value)
    return values[0] if values else None


def _multilingual_list(value: Any) -> list[str]:
    if isinstance(value, dict):
        preferred = value.get("eng") or value.get("ENG")
        if preferred:
            return [text for item in preferred if (text := clean_string(item))]
        for items in value.values():
            if isinstance(items, list):
                names = [text for item in items if (text := clean_string(item))]
                if names:
                    return names
    if isinstance(value, list):
        return [text for item in value if (text := clean_string(item))]
    text = clean_string(value)
    return [text] if text else []


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _transaction_type(cpv_codes: list[str], text: str) -> str:
    lowered = text.lower()
    if any(code.startswith(NUCLEAR_CPV_PREFIXES) for code in cpv_codes):
        return "fuel_supply"
    if any(term in lowered for term in ("construction", "engineering", "refurbishment", "maintenance")):
        return "construction_refurbishment"
    if any(term in lowered for term in ("finance", "financing", "grant", "investment")):
        return "financing"
    return "contract_award"


def _matched_terms(cpv_codes: list[str], text: str) -> list[str]:
    terms = []
    lowered = text.lower()
    for term in ("nuclear", "reactor", "uranium", "procurement", "tender"):
        if term in lowered:
            terms.append(term)
    terms.extend(code for code in cpv_codes if code.startswith(NUCLEAR_CPV_PREFIXES))
    return list(dict.fromkeys(terms))


def _title(*, publication_number: str, notice_type: str, buyer: str | None, winner: str | None) -> str:
    actor = buyer or "buyer"
    winner_part = f" awarded to {winner}" if winner else " public procurement notice"
    return f"TED {notice_type} {publication_number}: {actor}{winner_part}"


def _summary(
    *,
    notice_type: str,
    buyer: str | None,
    winner: str | None,
    country_name: str | None,
    amount_text: str | None,
) -> str:
    buyer_part = buyer or "Public buyer"
    location_part = f" in {country_name}" if country_name else ""
    winner_part = f" awarded to {winner}" if winner else " published a tender/procurement notice"
    amount_part = f" with value {amount_text}" if amount_text else ""
    return truncate_text(f"{buyer_part}{location_part}{winner_part}{amount_part}. Notice type: {notice_type}.", 240)


def _document_content(notice: dict[str, Any], *, url: str) -> str:
    buyer = _multilingual_first(notice.get("buyer-name")) or ""
    winners = ", ".join(_multilingual_list(notice.get("winner-name")))
    cpv = ", ".join(clean_string(value) or "" for value in (notice.get("classification-cpv") or []))
    amount = money_text(coerce_float(_first(notice.get("total-value")) or notice.get("total-value")), _first(notice.get("total-value-cur")) or "EUR")
    lines = [
        f"Publication number: {clean_string(notice.get('publication-number')) or ''}",
        f"Publication date: {clean_string(notice.get('publication-date')) or ''}",
        f"Notice type: {clean_string(notice.get('notice-type')) or ''}",
        f"Buyer: {buyer}",
        f"Winner: {winners}",
        f"Buyer country: {clean_string(_first(notice.get('buyer-country'))) or ''}",
        f"Total value: {amount or ''}",
        f"CPV codes: {cpv}",
        f"Source URL: {url}",
    ]
    return "\n".join(lines)
