from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    supabase_url: Optional[str] = Field(default=None, alias="SUPABASE_URL")
    rss_feeds: list[str] = Field(default_factory=list, alias="RSS_FEEDS")

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
    values["RSS_FEEDS"] = _split_csv_env(os.environ.get("RSS_FEEDS"))
    return Settings.model_validate(values)
