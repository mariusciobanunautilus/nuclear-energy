from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RSS_FEEDS = [
    "https://world-nuclear-news.org/rss",
    "https://www.ans.org/news/feed/",
    "https://www.iaea.org/feeds/topnews",
    "https://www.nrc.gov/public-involve/rss?feed=news",
    "https://www.nrc.gov/public-involve/rss?feed=plant-status",
]
DEFAULT_WATCHLIST_ENTITIES = [
    "Westinghouse Electric Company",
    "Cameco",
    "Centrus Energy",
    "Orano",
    "Framatome",
    "Urenco",
    "Kazatomprom",
    "Rosatom",
    "EDF",
    "Nuclearelectrica",
    "Bruce Power",
    "Ontario Power Generation",
    "Rolls-Royce SMR",
    "TerraPower",
    "X-energy",
    "NuScale Power",
]
DEFAULT_WATCHLIST_PROJECTS = [
    "Cernavoda",
    "Dukovany",
    "Sizewell C",
    "Hinkley Point C",
    "Vogtle",
    "Bruce",
    "Barakah",
    "Olkiluoto",
    "Flamanville",
    "Paks",
    "Kozloduy",
    "Zaporizhzhia",
]
DEFAULT_WATCHLIST_COUNTRIES = [
    "USA",
    "CAN",
    "FRA",
    "GBR",
    "ROU",
    "CZE",
    "POL",
    "BGR",
    "UKR",
    "RUS",
    "CHN",
    "JPN",
    "KOR",
    "KAZ",
]
DEFAULT_WATCHLIST_THEMES = [
    "fuel_cycle",
    "policy",
    "regulation",
    "project_stage",
    "construction",
    "operations",
    "project_risk",
    "supply_risk",
    "procurement",
    "financing",
]


class Settings(BaseModel):
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    supabase_url: Optional[str] = Field(default=None, alias="SUPABASE_URL")
    rss_feeds: list[str] = Field(default_factory=lambda: DEFAULT_RSS_FEEDS.copy(), alias="RSS_FEEDS")
    watchlist_entities: list[str] = Field(default_factory=lambda: DEFAULT_WATCHLIST_ENTITIES.copy(), alias="WATCHLIST_ENTITIES")
    watchlist_projects: list[str] = Field(default_factory=lambda: DEFAULT_WATCHLIST_PROJECTS.copy(), alias="WATCHLIST_PROJECTS")
    watchlist_countries: list[str] = Field(default_factory=lambda: DEFAULT_WATCHLIST_COUNTRIES.copy(), alias="WATCHLIST_COUNTRIES")
    watchlist_themes: list[str] = Field(default_factory=lambda: DEFAULT_WATCHLIST_THEMES.copy(), alias="WATCHLIST_THEMES")

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
    )


def _load_env_files() -> None:
    seen_dirs: set[Path] = set()
    for directory in (Path.cwd(), ROOT_DIR):
        if directory in seen_dirs:
            continue
        seen_dirs.add(directory)
        for filename in (".env", ".env.local"):
            path = directory / filename
            if path.exists():
                load_dotenv(path, override=False)


def _split_csv_env(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_env_files()
    values = dict(os.environ)
    values["RSS_FEEDS"] = _split_csv_env(os.environ.get("RSS_FEEDS")) or DEFAULT_RSS_FEEDS
    values["WATCHLIST_ENTITIES"] = _split_csv_env(os.environ.get("WATCHLIST_ENTITIES")) or DEFAULT_WATCHLIST_ENTITIES
    values["WATCHLIST_PROJECTS"] = _split_csv_env(os.environ.get("WATCHLIST_PROJECTS")) or DEFAULT_WATCHLIST_PROJECTS
    values["WATCHLIST_COUNTRIES"] = _split_csv_env(os.environ.get("WATCHLIST_COUNTRIES")) or DEFAULT_WATCHLIST_COUNTRIES
    values["WATCHLIST_THEMES"] = _split_csv_env(os.environ.get("WATCHLIST_THEMES")) or DEFAULT_WATCHLIST_THEMES
    return Settings.model_validate(values)
