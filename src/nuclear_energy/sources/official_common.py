from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any

from nuclear_energy.extraction.transactions import (
    COUNTRY_ALIASES,
    PLANT_ALIASES,
    _contains_term,
    _country_for_iso_code,
    _normalise_text,
)


USER_AGENT = "nuclear-energy-intelligence/0.1"


def clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def compact_text(*parts: Any) -> str:
    return " ".join(text for part in parts if (text := clean_string(part)))


def truncate_text(value: str, limit: int = 220) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3].rstrip()}..."


def parse_date(value: Any) -> datetime | None:
    text = clean_string(value)
    if not text:
        return None

    date_text = text[:10]
    for date_format in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            date_value = datetime.strptime(date_text, date_format).date()
            return datetime.combine(date_value, time.min, tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def infer_location(
    text: str,
    *,
    default_iso_code: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    normalised_text = _normalise_text(text)
    plants = [
        plant
        for plant in PLANT_ALIASES
        if any(_contains_term(normalised_text, alias) for alias in plant.aliases)
    ]
    countries = [
        country
        for country in COUNTRY_ALIASES
        if any(_contains_term(normalised_text, alias) for alias in country.aliases)
    ]
    for plant in plants:
        if plant.iso_code not in {country.iso_code for country in countries}:
            country = _country_for_iso_code(plant.iso_code)
            if country:
                countries.append(country)

    if not countries and default_iso_code:
        country = _country_for_iso_code(default_iso_code)
        if country:
            countries.append(country)

    country = countries[0] if countries else None
    plant = plants[0] if plants else None
    return (
        country.iso_code if country else None,
        country.country_name if country else None,
        plant.plant_name if plant else None,
    )


def money_text(amount: float | int | None, currency: str = "USD") -> str | None:
    if amount is None:
        return None
    return f"{currency} {float(amount):,.2f}"


def coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
