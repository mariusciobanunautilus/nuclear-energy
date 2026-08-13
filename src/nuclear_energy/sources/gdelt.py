from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from nuclear_energy.models import RawDocument, SourceKind


GDELT_DOC_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_GDELT_QUERY = '"nuclear energy" OR "nuclear power" OR reactor OR uranium'
USER_AGENT = "nuclear-energy-intelligence/0.1"


def fetch_gdelt_documents(
    *,
    query: str = DEFAULT_GDELT_QUERY,
    limit: int = 25,
    timespan: str = "1week",
    timeout: float = 20.0,
) -> list[RawDocument]:
    if limit < 1:
        return []

    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": min(limit, 250),
        "sort": "datedesc",
        "timespan": timespan,
    }
    response = httpx.get(
        GDELT_DOC_API_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()

    documents = []
    for article in payload.get("articles", []):
        document = _article_to_document(article)
        if document:
            documents.append(document)
        if len(documents) >= limit:
            break

    return documents


def _article_to_document(article: dict[str, Any]) -> RawDocument | None:
    url = _clean_string(article.get("url"))
    if not url:
        return None

    title = _clean_string(article.get("title")) or url
    domain = _clean_string(article.get("domain"))
    language = _clean_string(article.get("language"))
    source_country = _clean_string(article.get("sourcecountry"))

    tags = [value for value in (domain, language, source_country) if value]
    summary_parts = []
    if domain:
        summary_parts.append(f"Domain: {domain}")
    if language:
        summary_parts.append(f"Language: {language}")
    if source_country:
        summary_parts.append(f"Source country: {source_country}")

    return RawDocument(
        source_kind=SourceKind.gdelt,
        source_name="GDELT DOC 2.0",
        external_id=url,
        title=title,
        url=url,
        published_at=_parse_gdelt_datetime(article.get("seendate")),
        summary="; ".join(summary_parts) or None,
        authors=[],
        tags=tags,
        raw_payload=article,
    )


def _parse_gdelt_datetime(value: Any) -> datetime | None:
    text = _clean_string(value)
    if not text:
        return None

    formats = [
        "%Y%m%d%H%M%S",
        "%Y%m%dT%H%M%SZ",
        "%Y%m%dT%H%M%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for date_format in formats:
        try:
            return datetime.strptime(text, date_format).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
