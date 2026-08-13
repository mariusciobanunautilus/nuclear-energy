from __future__ import annotations

import argparse

from nuclear_energy.config import get_settings
from nuclear_energy.db import fetch_documents_without_chunks, replace_document_chunks, upsert_documents
from nuclear_energy.extraction.text import chunk_text, fetch_article_text
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


def _extract_documents(args: argparse.Namespace) -> int:
    documents = fetch_documents_without_chunks(limit=args.limit, source_name=args.source_name)
    if not documents:
        print("No documents need extraction.")
        return 0

    extracted = 0
    failed = 0
    total_chunks = 0

    for document in documents:
        try:
            try:
                text = document.content or fetch_article_text(document.url, timeout=args.timeout)
            except Exception:
                if not document.summary:
                    raise
                text = document.summary
            chunks = chunk_text(text, max_chars=args.max_chars, overlap=args.overlap)
            if not chunks:
                failed += 1
                print(f"Skipped document with no extractable text: {document.title}")
                continue

            stored_chunks = replace_document_chunks(document.id, text, chunks)
            extracted += 1
            total_chunks += stored_chunks
            print(f"Extracted {stored_chunks} chunk(s): {document.title}")
        except Exception as exc:
            failed += 1
            print(f"Failed extraction: {document.title} ({exc})")

    print(f"Extracted {extracted} document(s) into {total_chunks} chunk(s); {failed} failed/skipped.")
    return 0 if extracted or not failed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nuclear-energy")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_rss = subparsers.add_parser("ingest-rss", help="Fetch configured RSS feeds and store documents.")
    ingest_rss.add_argument("--feed", action="append", help="RSS feed URL. May be repeated.")
    ingest_rss.add_argument("--limit", type=int, default=25, help="Maximum entries per feed.")
    ingest_rss.set_defaults(func=_ingest_rss)

    extract_documents = subparsers.add_parser(
        "extract-documents",
        help="Fetch article URLs, extract clean text, and store document chunks.",
    )
    extract_documents.add_argument("--limit", type=int, default=10, help="Maximum documents to extract.")
    extract_documents.add_argument("--max-chars", type=int, default=2500, help="Maximum characters per chunk.")
    extract_documents.add_argument("--overlap", type=int, default=250, help="Character overlap between chunks.")
    extract_documents.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout per article.")
    extract_documents.add_argument("--source-name", help="Only extract documents from this exact source name.")
    extract_documents.set_defaults(func=_extract_documents)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
