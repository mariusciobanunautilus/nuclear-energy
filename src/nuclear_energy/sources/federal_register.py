from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any

import httpx

from nuclear_energy.models import RawDocument, SourceKind


FEDERAL_REGISTER_DOCUMENTS_URL = "https://www.federalregister.gov/api/v1/documents.json"
DEFAULT_FEDERAL_REGISTER_QUERY = "nuclear energy OR nuclear power OR reactor OR uranium"
USER_AGENT = "nuclear-energy-intelligence/0.1"


def fetch_federal_register_documents(
    *,
    query: str = DEFAULT_FEDERAL_REGISTER_QUERY,
    limit: int = 25,
    timeout: float = 20.0,
) -> list[RawDocument]:
    if limit < 1:
        return []

    params = {
        "conditions[term]": query,
        "order": "newest",
        "per_page": min(limit, 1000),
    }
    response = httpx.get(
        FEDERAL_REGISTER_DOCUMENTS_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()

    documents = []
    for result in payload.get("results", []):
        document = _result_to_document(result)
        if document:
            documents.append(document)
        if len(documents) >= limit:
            break

    return documents


def _result_to_document(result: dict[str, Any]) -> RawDocument | None:
    url = _clean_string(result.get("html_url")) or _clean_string(result.get("pdf_url"))
    if not url:
        return None

    document_number = _clean_string(result.get("document_number")) or url
    agencies = _agency_names(result.get("agencies"))
    tags = _tags(result)

    return RawDocument(
        source_kind=SourceKind.federal_register,
        source_name="Federal Register",
        external_id=document_number,
        title=_clean_string(result.get("title")) or document_number,
        url=url,
        published_at=_parse_publication_date(result.get("publication_date")),
        summary=_clean_string(result.get("abstract")) or _clean_string(result.get("excerpts")),
        authors=agencies,
        tags=tags,
        raw_payload=result,
    )


def _agency_names(agencies: Any) -> list[str]:
    if not isinstance(agencies, list):
        return []

    names = []
    for agency in agencies:
        if isinstance(agency, dict):
            name = _clean_string(agency.get("name"))
            if name:
                names.append(name)
    return names


def _tags(result: dict[str, Any]) -> list[str]:
    tags = []
    for value in (result.get("type"), result.get("subtype")):
        text = _clean_string(value)
        if text:
            tags.append(text)

    for topic in result.get("topics") or []:
        if isinstance(topic, dict):
            name = _clean_string(topic.get("name"))
            if name:
                tags.append(name)
        else:
            name = _clean_string(topic)
            if name:
                tags.append(name)

    return tags


def _parse_publication_date(value: Any) -> datetime | None:
    text = _clean_string(value)
    if not text:
        return None
    try:
        date_value = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None
    return datetime.combine(date_value, time.min, tzinfo=timezone.utc)


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
