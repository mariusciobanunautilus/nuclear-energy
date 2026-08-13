from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class SourceKind(str, Enum):
    rss = "rss"
    gdelt = "gdelt"
    eur_lex = "eur_lex"
    congress = "congress"
    federal_register = "federal_register"
    regulations_gov = "regulations_gov"


class RawDocument(BaseModel):
    source_kind: SourceKind
    source_name: str
    external_id: str
    title: str
    url: HttpUrl
    published_at: Optional[datetime] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @property
    def url_text(self) -> str:
        return str(self.url)
