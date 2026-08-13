from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any

import httpx

from nuclear_energy.models import RawDocument, SourceKind


CELLAR_SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
DEFAULT_EUR_LEX_QUERY = "nuclear reactor uranium energy"
USER_AGENT = "nuclear-energy-intelligence/0.1"


def fetch_eur_lex_documents(
    *,
    query: str = DEFAULT_EUR_LEX_QUERY,
    limit: int = 25,
    timeout: float = 30.0,
) -> list[RawDocument]:
    if limit < 1:
        return []

    terms = _query_terms(query)
    if not terms:
        return []

    response = httpx.get(
        CELLAR_SPARQL_URL,
        params={
            "query": _build_sparql_query(terms, limit=min(limit, 100)),
            "format": "application/sparql-results+json",
        },
        headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": USER_AGENT,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()

    documents = []
    for binding in payload.get("results", {}).get("bindings", []):
        document = _binding_to_document(binding)
        if document:
            documents.append(document)
        if len(documents) >= limit:
            break

    return documents


def _build_sparql_query(terms: list[str], limit: int) -> str:
    title_filters = " || ".join(
        f"CONTAINS(LCASE(STR(?title)), \"{term}\")"
        for term in terms
    )
    return f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd:<http://www.w3.org/2001/XMLSchema#>

select distinct ?work ?type ?celex ?title ?date where {{
  ?work cdm:resource_legal_id_celex ?celex.
  ?work cdm:work_has_resource-type ?type.
  OPTIONAL {{ ?work cdm:work_date_document ?date. }}
  ?exp cdm:expression_belongs_to_work ?work;
       cdm:expression_title ?title;
       cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG>.
  FILTER({title_filters})
  FILTER not exists{{?work cdm:do_not_index "true"^^xsd:boolean}}.
}}
order by desc(?date)
limit {limit}
"""


def _binding_to_document(binding: dict[str, Any]) -> RawDocument | None:
    celex = _binding_value(binding, "celex")
    if not celex:
        return None

    title = _binding_value(binding, "title") or celex
    resource_type = _resource_type_label(_binding_value(binding, "type"))
    date = _parse_date(_binding_value(binding, "date"))
    work_uri = _binding_value(binding, "work")
    url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"

    tags = [tag for tag in (resource_type, celex[:1] if celex else None) if tag]
    summary_parts = []
    if resource_type:
        summary_parts.append(f"Resource type: {resource_type}")
    if work_uri:
        summary_parts.append(f"Cellar work URI: {work_uri}")
    summary = "; ".join(summary_parts) or None
    content = title
    if summary:
        content = f"{title}\n\n{summary}"

    return RawDocument(
        source_kind=SourceKind.eur_lex,
        source_name="EUR-Lex",
        external_id=celex,
        title=title,
        url=url,
        published_at=date,
        summary=summary,
        content=content,
        authors=[],
        tags=tags,
        raw_payload={key: _binding_value(binding, key) for key in binding},
    )


def _query_terms(query: str) -> list[str]:
    terms = []
    current = []
    for character in query.lower():
        if character.isalnum():
            current.append(character)
        elif current:
            term = "".join(current)
            if len(term) >= 3:
                terms.append(term)
            current = []
    if current:
        term = "".join(current)
        if len(term) >= 3:
            terms.append(term)
    return list(dict.fromkeys(terms))


def _binding_value(binding: dict[str, Any], key: str) -> str | None:
    value = binding.get(key, {}).get("value")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resource_type_label(value: str | None) -> str | None:
    if not value:
        return None
    return value.rstrip("/").split("/")[-1]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        date_value = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return datetime.combine(date_value, time.min, tzinfo=timezone.utc)
