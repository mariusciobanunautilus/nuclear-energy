from __future__ import annotations

from io import StringIO
from math import isfinite
from typing import Any

import httpx
import pandas as pd

from nuclear_energy.models import CountryEnergyYear


EMBER_YEARLY_ELECTRICITY_URL = (
    "https://files.ember-energy.org/public-downloads/generation/outputs/"
    "release_generation_yearly_global.csv"
)
USER_AGENT = "nuclear-energy-intelligence/0.1"

COUNTRY_AREA_TYPE = "Country or economy"
INCLUDED_SOURCES = {
    "Clean",
    "Demand",
    "Fossil",
    "Net imports",
    "Nuclear",
    "Renewables",
    "Total generation",
}
REQUIRED_COLUMNS = {
    "Area",
    "ISO 3 code",
    "Year",
    "Area type",
    "Electricity source",
    "Generation (TWh)",
    "Share of generation (%)",
    "Capacity (GW)",
}


def fetch_ember_yearly_electricity(
    *,
    url: str = EMBER_YEARLY_ELECTRICITY_URL,
    since_year: int = 2000,
    iso_codes: list[str] | None = None,
    timeout: float = 30.0,
) -> list[CountryEnergyYear]:
    response = httpx.get(
        url,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_ember_yearly_electricity_csv(
        response.text,
        source_url=url,
        since_year=since_year,
        iso_codes=iso_codes,
    )


def parse_ember_yearly_electricity_csv(
    csv_text: str,
    *,
    source_url: str = EMBER_YEARLY_ELECTRICITY_URL,
    since_year: int = 2000,
    iso_codes: list[str] | None = None,
) -> list[CountryEnergyYear]:
    frame = pd.read_csv(StringIO(csv_text), usecols=lambda column: column in REQUIRED_COLUMNS)
    missing_columns = REQUIRED_COLUMNS.difference(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Ember yearly electricity CSV is missing column(s): {missing}")

    frame = frame.rename(
        columns={
            "Area": "country_name",
            "ISO 3 code": "iso_code",
            "Year": "year",
            "Area type": "area_type",
            "Electricity source": "electricity_source",
            "Generation (TWh)": "generation_twh",
            "Share of generation (%)": "share_of_generation_percent",
            "Capacity (GW)": "capacity_gw",
        }
    )
    frame = frame[
        frame["area_type"].eq(COUNTRY_AREA_TYPE)
        & frame["iso_code"].notna()
        & frame["electricity_source"].isin(INCLUDED_SOURCES)
        & frame["year"].ge(since_year)
    ].copy()

    requested_iso_codes = _normalise_iso_codes(iso_codes)
    if requested_iso_codes:
        frame = frame[frame["iso_code"].str.upper().isin(requested_iso_codes)]

    if frame.empty:
        return []

    rows = [_group_to_energy_year(key, group, source_url=source_url) for key, group in _country_year_groups(frame)]
    nuclear_iso_codes = {
        row.iso_code
        for row in rows
        if _positive(row.nuclear_generation_twh) or _positive(row.nuclear_capacity_gw)
    }
    if requested_iso_codes:
        nuclear_iso_codes.update(requested_iso_codes)

    return [
        row
        for row in rows
        if row.iso_code in nuclear_iso_codes
        and (
            row.nuclear_generation_twh is not None
            or row.nuclear_capacity_gw is not None
            or row.electricity_demand_twh is not None
            or row.net_electricity_imports_twh is not None
        )
    ]


def _country_year_groups(frame: pd.DataFrame):
    sorted_frame = frame.sort_values(["country_name", "iso_code", "year", "electricity_source"])
    yield from sorted_frame.groupby(["country_name", "iso_code", "year"], sort=False)


def _group_to_energy_year(key: tuple[str, str, int], group: pd.DataFrame, *, source_url: str) -> CountryEnergyYear:
    country_name, iso_code, year = key
    by_source: dict[str, dict[str, Any]] = {}
    for row in group.to_dict(orient="records"):
        source = str(row["electricity_source"])
        by_source[source] = {
            "generation_twh": _optional_float(row.get("generation_twh")),
            "share_of_generation_percent": _optional_float(row.get("share_of_generation_percent")),
            "capacity_gw": _optional_float(row.get("capacity_gw")),
        }

    return CountryEnergyYear(
        country_name=str(country_name).strip(),
        iso_code=str(iso_code).strip().upper(),
        year=int(year),
        nuclear_generation_twh=_source_metric(by_source, "Nuclear", "generation_twh"),
        nuclear_share_electricity_percent=_source_metric(by_source, "Nuclear", "share_of_generation_percent"),
        nuclear_capacity_gw=_source_metric(by_source, "Nuclear", "capacity_gw"),
        electricity_generation_twh=_source_metric(by_source, "Total generation", "generation_twh"),
        electricity_demand_twh=_source_metric(by_source, "Demand", "generation_twh"),
        net_electricity_imports_twh=_source_metric(by_source, "Net imports", "generation_twh"),
        fossil_generation_twh=_source_metric(by_source, "Fossil", "generation_twh"),
        renewables_generation_twh=_source_metric(by_source, "Renewables", "generation_twh"),
        clean_generation_twh=_source_metric(by_source, "Clean", "generation_twh"),
        source_url=source_url,
        raw_payload={"ember_sources": by_source},
    )


def _source_metric(
    by_source: dict[str, dict[str, float | None]],
    source: str,
    metric: str,
) -> float | None:
    values = by_source.get(source)
    if not values:
        return None
    return values.get(metric)


def _normalise_iso_codes(iso_codes: list[str] | None) -> set[str]:
    if not iso_codes:
        return set()
    return {code.strip().upper() for code in iso_codes if code.strip()}


def _positive(value: float | None) -> bool:
    return value is not None and value > 0


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number):
        return None
    return number
