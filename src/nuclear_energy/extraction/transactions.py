from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from nuclear_energy.models import NuclearTransaction


class TransactionDocument(Protocol):
    id: str
    title: str
    url: str
    source_name: str
    source_kind: str
    published_at: datetime | None
    summary: str | None
    content: str | None


@dataclass(frozen=True)
class CountryAlias:
    iso_code: str
    country_name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class PlantAlias:
    plant_name: str
    iso_code: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class TransactionTermGroup:
    transaction_type: str
    terms: tuple[str, ...]


COUNTRY_ALIASES = (
    CountryAlias("ARG", "Argentina", ("argentina", "argentine")),
    CountryAlias("ARM", "Armenia", ("armenia", "armenian")),
    CountryAlias("ARE", "United Arab Emirates", ("united arab emirates", "uae", "emirati")),
    CountryAlias("BEL", "Belgium", ("belgium", "belgian")),
    CountryAlias("BGR", "Bulgaria", ("bulgaria", "bulgarian")),
    CountryAlias("BRA", "Brazil", ("brazil", "brazilian")),
    CountryAlias("CAN", "Canada", ("canada", "canadian")),
    CountryAlias("CHE", "Switzerland", ("switzerland", "swiss")),
    CountryAlias("CHN", "China", ("china", "chinese")),
    CountryAlias("CZE", "Czechia", ("czechia", "czech republic", "czech")),
    CountryAlias("DEU", "Germany", ("germany", "german")),
    CountryAlias("ESP", "Spain", ("spain", "spanish")),
    CountryAlias("FIN", "Finland", ("finland", "finnish")),
    CountryAlias("FRA", "France", ("france", "french")),
    CountryAlias("GBR", "United Kingdom", ("united kingdom", "uk ", "britain", "british", "england")),
    CountryAlias("HUN", "Hungary", ("hungary", "hungarian")),
    CountryAlias("IND", "India", ("india", "indian")),
    CountryAlias("JPN", "Japan", ("japan", "japanese")),
    CountryAlias("KOR", "South Korea", ("south korea", "korea", "korean")),
    CountryAlias("MEX", "Mexico", ("mexico", "mexican")),
    CountryAlias("NLD", "Netherlands", ("netherlands", "dutch")),
    CountryAlias("PAK", "Pakistan", ("pakistan", "pakistani")),
    CountryAlias("POL", "Poland", ("poland", "polish")),
    CountryAlias("ROU", "Romania", ("romania", "romanian", "nuclearelectrica")),
    CountryAlias("RUS", "Russia", ("russia", "russian", "rosatom")),
    CountryAlias("SVK", "Slovakia", ("slovakia", "slovak")),
    CountryAlias("SVN", "Slovenia", ("slovenia", "slovenian")),
    CountryAlias("SWE", "Sweden", ("sweden", "swedish")),
    CountryAlias("UKR", "Ukraine", ("ukraine", "ukrainian")),
    CountryAlias("USA", "United States", ("united states", "u.s.", " us ", "usa", "american")),
    CountryAlias("ZAF", "South Africa", ("south africa", "south african")),
)

PLANT_ALIASES = (
    PlantAlias("Barakah", "ARE", ("barakah",)),
    PlantAlias("Bruce", "CAN", ("bruce", "bruce power")),
    PlantAlias("Cernavoda", "ROU", ("cernavoda",)),
    PlantAlias("Dukovany", "CZE", ("dukovany",)),
    PlantAlias("Flamanville", "FRA", ("flamanville",)),
    PlantAlias("Hinkley Point C", "GBR", ("hinkley point c", "hinkley point")),
    PlantAlias("Kashiwazaki-Kariwa", "JPN", ("kashiwazaki-kariwa", "kashiwazaki kariwa")),
    PlantAlias("Khmelnitskiy", "UKR", ("khmelnitskiy", "khmelnytskyi")),
    PlantAlias("Kozloduy", "BGR", ("kozloduy",)),
    PlantAlias("Olkiluoto", "FIN", ("olkiluoto",)),
    PlantAlias("Paks", "HUN", ("paks",)),
    PlantAlias("Sizewell C", "GBR", ("sizewell c", "sizewell")),
    PlantAlias("Temelin", "CZE", ("temelin",)),
    PlantAlias("Vogtle", "USA", ("vogtle",)),
    PlantAlias("Watts Bar", "USA", ("watts bar",)),
    PlantAlias("Zaporizhzhia", "UKR", ("zaporizhzhia", "zaporizhia")),
)

TERM_GROUPS = (
    TransactionTermGroup(
        "contract_award",
        (
            "award",
            "awards",
            "awarded",
            "agreement",
            "contract",
            "contract award",
            "procurement",
            "purchase order",
            "supplier",
            "tender",
        ),
    ),
    TransactionTermGroup(
        "financing",
        (
            "credit facility",
            "debt",
            "equity",
            "finance",
            "financing",
            "funding",
            "grant",
            "investment",
            "loan",
            "state aid",
            "subsidy",
        ),
    ),
    TransactionTermGroup(
        "construction_refurbishment",
        (
            "construction",
            "engineering",
            "epc",
            "life extension",
            "maintenance contract",
            "refurbishment",
            "restart",
            "service agreement",
        ),
    ),
    TransactionTermGroup(
        "fuel_supply",
        (
            "conversion",
            "enrichment",
            "fuel supply",
            "fuel",
            "offtake",
            "uranium",
            "uranium supply",
        ),
    ),
    TransactionTermGroup(
        "merger_acquisition",
        (
            "acquired",
            "acquires",
            "acquisition of",
            "asset sale",
            "joint venture",
            "merger",
            "purchase of",
            "sale of",
            "stake in",
        ),
    ),
)

MONEY_PATTERN = re.compile(
    r"(?P<prefix>\$|€|£|USD|EUR|GBP|CAD|C\$|US\$)\s*"
    r"(?P<number>\d+(?:[.,]\d+)?)\s*(?P<scale>billion|bn|million|m|thousand|k)?"
    r"|(?P<number2>\d+(?:[.,]\d+)?)\s*"
    r"(?P<scale2>billion|bn|million|m|thousand|k)?\s+"
    r"(?P<suffix>dollars|euros|pounds|usd|eur|gbp|cad|ron|lei)",
    re.IGNORECASE,
)

CURRENCY_ALIASES = {
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "dollars": "USD",
    "€": "EUR",
    "EUR": "EUR",
    "euros": "EUR",
    "£": "GBP",
    "GBP": "GBP",
    "pounds": "GBP",
    "CAD": "CAD",
    "C$": "CAD",
    "RON": "RON",
    "lei": "RON",
}

SCALE_MULTIPLIERS = {
    "billion": 1_000_000_000,
    "bn": 1_000_000_000,
    "million": 1_000_000,
    "m": 1_000_000,
    "thousand": 1_000,
    "k": 1_000,
}


def detect_nuclear_transactions(
    documents: Iterable[TransactionDocument],
    *,
    min_confidence: float = 0.45,
) -> list[NuclearTransaction]:
    candidates = []
    for document in documents:
        candidate = _detect_document_transaction(document)
        if candidate and candidate.confidence >= min_confidence:
            candidates.append(candidate)
    return candidates


def _detect_document_transaction(document: TransactionDocument) -> NuclearTransaction | None:
    text = _document_text(document)
    normalised_text = _normalise_text(text)
    matched_by_type = {
        group.transaction_type: _matched_terms(normalised_text, group.terms)
        for group in TERM_GROUPS
    }
    matched_by_type = {
        transaction_type: terms
        for transaction_type, terms in matched_by_type.items()
        if terms
    }
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

    transaction_type, matched_terms = _best_transaction_type(matched_by_type)
    amount_text, amount, currency = _extract_money(text)
    country = countries[0] if countries else None
    plant = plants[0] if plants else None
    confidence = _confidence_score(
        matched_terms=matched_terms,
        has_amount=amount_text is not None,
        has_country=country is not None,
        has_plant=plant is not None,
    )

    country_iso_code = country.iso_code if country else None
    country_name = country.country_name if country else None
    plant_name = plant.plant_name if plant else None
    title = document.title.strip()
    summary = _summary(
        title=title,
        transaction_type=transaction_type,
        country_name=country_name,
        plant_name=plant_name,
        amount_text=amount_text,
    )

    external_id = _external_id(
        document_id=document.id,
        transaction_type=transaction_type,
        country_iso_code=country_iso_code,
        amount_text=amount_text,
        matched_terms=matched_terms,
    )

    return NuclearTransaction(
        external_id=external_id,
        document_id=document.id,
        transaction_date=document.published_at,
        country_iso_code=country_iso_code,
        country_name=country_name,
        plant_name=plant_name,
        project_name=plant_name,
        transaction_type=transaction_type,
        title=title,
        summary=summary,
        source_name=document.source_name,
        source_url=document.url,
        amount_text=amount_text,
        amount=amount,
        currency=currency,
        matched_terms=matched_terms,
        confidence=confidence,
        raw_payload={
            "source_kind": document.source_kind,
            "matched_country_aliases": [country.iso_code for country in countries],
            "matched_plant_aliases": [plant.plant_name for plant in plants],
        },
    )


def _document_text(document: TransactionDocument) -> str:
    return "\n\n".join(
        part
        for part in (document.title, document.summary or "", document.content or "")
        if part
    )


def _match_countries(normalised_text: str) -> list[CountryAlias]:
    matches = []
    for country in COUNTRY_ALIASES:
        if any(_contains_term(normalised_text, alias) for alias in country.aliases):
            matches.append(country)
    return matches


def _match_plants(normalised_text: str) -> list[PlantAlias]:
    matches = []
    for plant in PLANT_ALIASES:
        if any(_contains_term(normalised_text, alias) for alias in plant.aliases):
            matches.append(plant)
    return matches


def _country_for_iso_code(iso_code: str) -> CountryAlias | None:
    for country in COUNTRY_ALIASES:
        if country.iso_code == iso_code:
            return country
    return None


def _matched_terms(normalised_text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if _contains_term(normalised_text, term)]


def _contains_term(normalised_text: str, term: str) -> bool:
    term = _normalise_text(term)
    if term.endswith(" "):
        return term in normalised_text
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalised_text) is not None


def _best_transaction_type(matched_by_type: dict[str, list[str]]) -> tuple[str, list[str]]:
    return max(
        matched_by_type.items(),
        key=lambda item: (len(item[1]), _transaction_type_priority(item[0])),
    )


def _transaction_type_priority(transaction_type: str) -> int:
    priorities = {
        "contract_award": 5,
        "financing": 4,
        "merger_acquisition": 3,
        "construction_refurbishment": 2,
        "fuel_supply": 1,
    }
    return priorities.get(transaction_type, 0)


def _extract_money(text: str) -> tuple[str | None, float | None, str | None]:
    match = MONEY_PATTERN.search(text)
    if not match:
        return None, None, None

    amount_text = match.group(0).strip()
    number_text = match.group("number") or match.group("number2")
    scale_text = match.group("scale") or match.group("scale2")
    currency_text = match.group("prefix") or match.group("suffix")
    number = _parse_number(number_text)
    if number is None:
        return amount_text, None, _normalise_currency(currency_text)

    multiplier = SCALE_MULTIPLIERS.get((scale_text or "").lower(), 1)
    return amount_text, number * multiplier, _normalise_currency(currency_text)


def _parse_number(value: str | None) -> float | None:
    if not value:
        return None
    normalised = value.replace(",", ".")
    try:
        return float(normalised)
    except ValueError:
        return None


def _normalise_currency(value: str | None) -> str | None:
    if not value:
        return None
    return CURRENCY_ALIASES.get(value.upper(), CURRENCY_ALIASES.get(value.lower(), value.upper()))


def _confidence_score(
    *,
    matched_terms: list[str],
    has_amount: bool,
    has_country: bool,
    has_plant: bool,
) -> float:
    score = 0.35 + min(len(matched_terms), 4) * 0.08
    if has_amount:
        score += 0.18
    if has_country:
        score += 0.12
    if has_plant:
        score += 0.12
    return min(score, 0.95)


def _summary(
    *,
    title: str,
    transaction_type: str,
    country_name: str | None,
    plant_name: str | None,
    amount_text: str | None,
) -> str:
    location = plant_name or country_name or "nuclear sector"
    amount_part = f" with a reported amount of {amount_text}" if amount_text else ""
    return f"{_transaction_label(transaction_type)} signal for {location}{amount_part}: {title}"


def _transaction_label(transaction_type: str) -> str:
    return transaction_type.replace("_", " ").title()


def _external_id(
    *,
    document_id: str,
    transaction_type: str,
    country_iso_code: str | None,
    amount_text: str | None,
    matched_terms: list[str],
) -> str:
    signature = "|".join(
        [
            document_id,
            transaction_type,
            country_iso_code or "",
            amount_text or "",
            ",".join(sorted(matched_terms)),
        ]
    )
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:24]
    return f"doc-{digest}"


def _normalise_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    return f" {value.lower()} "
