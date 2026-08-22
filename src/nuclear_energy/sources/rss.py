from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable

import feedparser

from nuclear_energy.models import RawDocument, SourceKind


KNOWN_FEED_TITLES = {
    "https://www.nrc.gov/public-involve/rss?feed=news": "NRC News Releases",
    "https://www.nrc.gov/public-involve/rss?feed=plant-status": "NRC Power Reactor Status",
    "https://api.io.canada.ca/io-server/gc/news/en/v2?dept=canadiannuclearsafetycommission&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-07-23&pick=25&format=atom&atomtitle=Canadian%20Nuclear%20Safety%20Commission": "Canadian Nuclear Safety Commission",
    "https://www.onr.org.uk/rss-news": "UK Office for Nuclear Regulation News",
    "https://www.onr.org.uk/rss-global": "UK Office for Nuclear Regulation Publications",
    "https://reglementation-controle.asnr.fr/rss/avis-incidents-INB": "ASNR Nuclear Installation Incident Notices",
    "https://reglementation-controle.asnr.fr/rss/arrets_reacteur": "ASNR Reactor Outages",
    "https://reglementation-controle.asnr.fr/rss/lettre-de-suite-inspection-INB": "ASNR Nuclear Installation Inspection Letters",
    "https://www.nuclearelectrica.ro/snn/en/feed/": "Nuclearelectrica News",
    "https://www.nuclearelectrica.ro/ir/en/feed/": "Nuclearelectrica Investor Relations",
}


def _get_value(item: object, key: str):
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _entry_datetime(entry: object) -> datetime | None:
    for key in ("published", "updated", "created"):
        value = _get_value(entry, key)
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _entry_authors(entry: object) -> list[str]:
    authors = _get_value(entry, "authors")
    if isinstance(authors, list):
        names = [item.get("name") for item in authors if isinstance(item, dict)]
        return [name for name in names if name]
    author = _get_value(entry, "author")
    return [author] if author else []


def _entry_tags(entry: object) -> list[str]:
    tags = _get_value(entry, "tags")
    if not isinstance(tags, list):
        return []
    values = [item.get("term") for item in tags if isinstance(item, dict)]
    return [value for value in values if value]


def fetch_rss_feed(feed_url: str, *, limit: int | None = None) -> list[RawDocument]:
    parsed = feedparser.parse(feed_url)
    source_name = KNOWN_FEED_TITLES.get(feed_url) or parsed.feed.get("title") or feed_url
    documents: list[RawDocument] = []

    entries: Iterable[object] = parsed.entries[:limit] if limit else parsed.entries
    for entry in entries:
        link = _get_value(entry, "link")
        title = _get_value(entry, "title")
        if not link or not title:
            continue

        external_id = _get_value(entry, "id") or _get_value(entry, "guid") or link
        summary = _get_value(entry, "summary")

        documents.append(
            RawDocument(
                source_kind=SourceKind.rss,
                source_name=source_name,
                external_id=external_id,
                title=title,
                url=link,
                published_at=_entry_datetime(entry),
                summary=summary,
                authors=_entry_authors(entry),
                tags=_entry_tags(entry),
            )
        )

    return documents


def fetch_rss_feeds(feed_urls: Iterable[str], *, limit_per_feed: int | None = None) -> list[RawDocument]:
    documents: list[RawDocument] = []
    for feed_url in feed_urls:
        documents.extend(fetch_rss_feed(feed_url, limit=limit_per_feed))
    return documents
