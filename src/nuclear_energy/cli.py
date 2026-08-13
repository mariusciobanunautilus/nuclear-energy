from __future__ import annotations

import argparse

from nuclear_energy.config import get_settings
from nuclear_energy.db import upsert_documents
from nuclear_energy.sources.rss import fetch_rss_feeds


def _ingest_rss(args: argparse.Namespace) -> int:
    settings = get_settings()
    feeds = args.feed or settings.rss_feeds
    if not feeds:
        raise SystemExit("No RSS feeds configured. Set RSS_FEEDS or pass --feed.")

    documents = fetch_rss_feeds(feeds, limit_per_feed=args.limit)
    stored = upsert_documents(documents)
    print(f"Stored {stored} RSS documents from {len(feeds)} feed(s).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nuclear-energy")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_rss = subparsers.add_parser("ingest-rss", help="Fetch configured RSS feeds and store documents.")
    ingest_rss.add_argument("--feed", action="append", help="RSS feed URL. May be repeated.")
    ingest_rss.add_argument("--limit", type=int, default=25, help="Maximum entries per feed.")
    ingest_rss.set_defaults(func=_ingest_rss)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
