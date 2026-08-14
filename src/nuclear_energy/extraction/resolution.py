from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class EntityAlias:
    canonical_name: str
    entity_type: str
    aliases: tuple[str, ...]
    country_iso_code: str | None = None


KNOWN_ENTITY_ALIASES = (
    EntityAlias("U.S. Department of Energy", "government_agency", ("department of energy", "u.s. doe", "us doe", "doe"), "USA"),
    EntityAlias("U.S. Nuclear Regulatory Commission", "regulator", ("nuclear regulatory commission", "nrc", "u.s. nrc"), "USA"),
    EntityAlias("EURATOM", "regulator", ("euratom",), None),
    EntityAlias("International Atomic Energy Agency", "regulator", ("iaea", "international atomic energy agency"), None),
    EntityAlias("EDF", "utility", ("edf", "electricite de france", "electricite de france"), "FRA"),
    EntityAlias("Orano", "company", ("orano", "areva"), "FRA"),
    EntityAlias("Framatome", "company", ("framatome",), "FRA"),
    EntityAlias("Westinghouse Electric Company", "company", ("westinghouse", "westinghouse electric"), "USA"),
    EntityAlias("Cameco", "company", ("cameco",), "CAN"),
    EntityAlias("Centrus Energy", "company", ("centrus", "american centrifuge", "american centrifuge operating"), "USA"),
    EntityAlias("Urenco", "company", ("urenco",), "GBR"),
    EntityAlias("Kazatomprom", "company", ("kazatomprom",), "KAZ"),
    EntityAlias("Rosatom", "company", ("rosatom",), "RUS"),
    EntityAlias("KHNP", "utility", ("khnp", "korea hydro & nuclear power", "korea hydro and nuclear power"), "KOR"),
    EntityAlias("Korea Electric Power Corporation", "utility", ("kepco", "korea electric power"), "KOR"),
    EntityAlias("Nuclearelectrica", "utility", ("nuclearelectrica", "snn nuclearelectrica"), "ROU"),
    EntityAlias("Bruce Power", "utility", ("bruce power",), "CAN"),
    EntityAlias("Ontario Power Generation", "utility", ("ontario power generation", "opg"), "CAN"),
    EntityAlias("Rolls-Royce SMR", "company", ("rolls-royce smr", "rolls royce smr"), "GBR"),
    EntityAlias("TerraPower", "company", ("terrapower",), "USA"),
    EntityAlias("X-energy", "company", ("x-energy", "x energy"), "USA"),
    EntityAlias("NuScale Power", "company", ("nuscale", "nuscale power"), "USA"),
    EntityAlias("China National Nuclear Corporation", "company", ("cnnc", "china national nuclear corporation"), "CHN"),
)


def match_entity_mentions(text: str) -> list[dict[str, str | None]]:
    normalised_text = _normalise_text(text)
    matches = []
    for entity in KNOWN_ENTITY_ALIASES:
        matched_aliases = [alias for alias in entity.aliases if _contains_term(normalised_text, alias)]
        if matched_aliases:
            matches.append(
                {
                    "canonical_name": entity.canonical_name,
                    "entity_type": entity.entity_type,
                    "country_iso_code": entity.country_iso_code,
                    "matched_aliases": ", ".join(matched_aliases),
                }
            )
    return matches


def _contains_term(normalised_text: str, term: str) -> bool:
    term = _normalise_text(term).strip()
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalised_text) is not None


def _normalise_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    return f" {value.lower()} "
