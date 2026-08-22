from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from io import StringIO
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

from nuclear_energy.models import LiveGenerationSnapshot


TRANSELECTRICA_LIVE_GENERATION_URL = "https://www.sistemulenergetic.ro/"
TRANSELECTRICA_SEN_URL = "https://www.transelectrica.ro/web/tel/sistemul-energetic-national"
USER_AGENT = "nuclear-energy-intelligence/0.1"
ROMANIA_TIMEZONE = ZoneInfo("Europe/Bucharest")

COLUMN_ALIASES = {
    "data": "observed_at",
    "putere ceruta": "demand_mw",
    "consum": "demand_mw",
    "putere debitata": "production_mw",
    "productie": "production_mw",
    "nuclear": "nuclear_mw",
    "eolian": "wind_mw",
    "vant": "wind_mw",
    "hidro": "hydro_mw",
    "hidrocarburi": "hydrocarbons_mw",
    "carbune": "coal_mw",
    "fotovoltaic": "solar_mw",
    "fotovolt": "solar_mw",
    "solar": "solar_mw",
    "biomasa": "biomass_mw",
    "stocare": "storage_mw",
    "sold": "net_import_export_mw",
    "sold schimb": "net_import_export_mw",
}


def fetch_transelectrica_live_generation(
    *,
    url: str = TRANSELECTRICA_LIVE_GENERATION_URL,
    timeout: float = 20.0,
) -> LiveGenerationSnapshot:
    response = httpx.get(
        url,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_transelectrica_live_generation_html(response.text, source_url=url)


def parse_transelectrica_live_generation_html(
    html: str,
    *,
    source_url: str = TRANSELECTRICA_LIVE_GENERATION_URL,
) -> LiveGenerationSnapshot:
    frames = pd.read_html(StringIO(html))
    candidate = _generation_table(frames)
    if candidate is None:
        raise ValueError("Transelectrica live generation table was not found.")

    frame = candidate.rename(columns={column: _field_for_column(column) for column in candidate.columns})
    frame = frame[[column for column in frame.columns if column]]
    if frame.empty:
        raise ValueError("Transelectrica live generation table is empty.")

    latest_row = frame.iloc[0].to_dict()
    observed_at = _parse_observed_at(latest_row.get("observed_at"))
    values = {
        field: _optional_int(latest_row.get(field))
        for field in (
            "demand_mw",
            "production_mw",
            "net_import_export_mw",
            "nuclear_mw",
            "wind_mw",
            "hydro_mw",
            "hydrocarbons_mw",
            "coal_mw",
            "solar_mw",
            "biomass_mw",
            "storage_mw",
        )
    }

    return LiveGenerationSnapshot(
        observed_at=observed_at,
        country_iso_code="ROU",
        country_name="Romania",
        source_url=source_url,
        **values,
        raw_payload={
            "source": "transelectrica_live_generation",
            "raw_row": _json_safe_row(latest_row),
            "source_page": TRANSELECTRICA_SEN_URL,
        },
    )


def _generation_table(frames: list[pd.DataFrame]) -> pd.DataFrame | None:
    for frame in frames:
        fields = {_field_for_column(column) for column in frame.columns}
        if {"observed_at", "demand_mw", "production_mw", "nuclear_mw"}.issubset(fields):
            return frame
    return None


def _field_for_column(column: Any) -> str | None:
    label = _normalise_label(column)
    if not label:
        return None
    for alias, field in sorted(COLUMN_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in label:
            return field
    return None


def _normalise_label(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"\[[^\]]+\]|\([^\)]*\)|\{[^\}]*\}|\^[^\s]+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_observed_at(value: Any) -> datetime:
    parsed = pd.to_datetime(value, dayfirst=False, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Could not parse Transelectrica timestamp: {value!r}")
    observed_at = parsed.to_pydatetime()
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=ROMANIA_TIMEZONE)
    return observed_at


def _optional_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value.replace("\xa0", " "))
        if not match:
            return None
        value = match.group(0).replace(",", ".")
    return int(round(float(value)))


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    for key, value in row.items():
        if pd.isna(value):
            safe[str(key)] = None
        elif isinstance(value, datetime):
            safe[str(key)] = value.isoformat()
        else:
            safe[str(key)] = value.item() if hasattr(value, "item") else value
    return safe
