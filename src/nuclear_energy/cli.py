from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import httpx
from openai import OpenAIError

from nuclear_energy.config import get_settings
from nuclear_energy.db import (
    fetch_chunks_needing_embeddings,
    fetch_documents_without_chunks,
    fetch_documents_for_export,
    replace_document_chunks,
    semantic_search_chunks,
    update_chunk_embeddings,
    upsert_documents,
)
from nuclear_energy.embeddings import (
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    create_embedding,
    create_embeddings,
    dimensions_for_model,
)
from nuclear_energy.exports import documents_to_csv, documents_to_markdown
from nuclear_energy.extraction.text import chunk_text, fetch_article_text
from nuclear_energy.sources.federal_register import (
    DEFAULT_FEDERAL_REGISTER_QUERY,
    fetch_federal_register_documents,
)
from nuclear_energy.sources.gdelt import DEFAULT_GDELT_QUERY, fetch_gdelt_documents
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


def _ingest_gdelt(args: argparse.Namespace) -> int:
    try:
        documents = fetch_gdelt_documents(
            query=args.query,
            limit=args.limit,
            timespan=args.timespan,
            timeout=args.timeout,
        )
    except httpx.HTTPError as exc:
        print(_describe_source_http_error("GDELT", exc))
        return 1
    stored = upsert_documents(documents)
    print(f"Stored {stored} GDELT document(s).")
    return 0


def _ingest_federal_register(args: argparse.Namespace) -> int:
    try:
        documents = fetch_federal_register_documents(
            query=args.query,
            limit=args.limit,
            timeout=args.timeout,
        )
    except httpx.HTTPError as exc:
        print(_describe_source_http_error("Federal Register", exc))
        return 1
    stored = upsert_documents(documents)
    print(f"Stored {stored} Federal Register document(s).")
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


def _embed_chunks(args: argparse.Namespace) -> int:
    chunks = fetch_chunks_needing_embeddings(limit=args.limit, model=args.model)
    if not chunks:
        print("No chunks need embeddings.")
        return 0

    total = 0
    dimensions = dimensions_for_model(args.model)

    for batch in _batched(chunks, args.batch_size):
        try:
            vectors = create_embeddings(
                [chunk.content for chunk in batch],
                model=args.model,
                dimensions=dimensions,
                batch_size=args.batch_size,
            )
        except (OpenAIError, RuntimeError) as exc:
            print(_describe_openai_error(exc))
            return 1
        total += update_chunk_embeddings(
            ((chunk.id, vector) for chunk, vector in zip(batch, vectors)),
            model=args.model,
        )
        print(f"Embedded {total}/{len(chunks)} chunk(s).")

    print(f"Stored embeddings for {total} chunk(s) using {args.model}.")
    return 0


def _search_chunks(args: argparse.Namespace) -> int:
    dimensions = dimensions_for_model(args.model)
    try:
        query_embedding = create_embedding(args.query, model=args.model, dimensions=dimensions)
    except (OpenAIError, RuntimeError) as exc:
        print(_describe_openai_error(exc))
        return 1

    results = semantic_search_chunks(
        query_embedding,
        limit=args.limit,
        source_name=args.source_name,
    )

    if not results:
        print("No embedded chunks matched. Run embed-chunks first.")
        return 0

    for index, result in enumerate(results, start=1):
        preview = result.content.replace("\n", " ")
        if len(preview) > args.preview_chars:
            preview = f"{preview[: args.preview_chars].rstrip()}..."
        print(f"{index}. score={result.score:.3f} chunk={result.chunk_index} {result.title}")
        print(f"   {result.url}")
        print(f"   {preview}")

    return 0


def _export_documents(args: argparse.Namespace) -> int:
    documents = fetch_documents_for_export(
        limit=args.limit,
        source_name=args.source_name,
        preview_chars=args.preview_chars,
    )
    if args.format == "csv":
        content = documents_to_csv(documents)
        default_name = "documents.csv"
    else:
        content = documents_to_markdown(documents)
        default_name = "documents.md"

    output_path = Path(args.output or Path("exports") / default_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Exported {len(documents)} document(s) to {output_path}.")
    return 0


def _dashboard(args: argparse.Namespace) -> int:
    dashboard_path = Path(__file__).with_name("dashboard.py")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(dashboard_path),
        "--server.address",
        args.address,
        "--server.port",
        str(args.port),
        "--server.headless",
        "true",
    ]
    return subprocess.call(command)


def _describe_openai_error(exc: Exception) -> str:
    message = str(exc)
    lower_message = message.lower()
    if "openai_api_key" in lower_message:
        return "OPENAI_API_KEY is missing. Add it to .env.local, then rerun this command."
    if (
        "credit_balance_exhausted" in lower_message
        or "insufficient_quota" in lower_message
        or "no credits" in lower_message
    ):
        return (
            "OpenAI API credits are exhausted. Add credits at "
            "https://platform.openai.com/settings/organization/billing, then rerun this command."
        )
    return f"OpenAI API request failed: {message}"


def _describe_source_http_error(source_name: str, exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 429:
            return f"{source_name} rate limit reached. Wait a few minutes, then rerun this command."
        return f"{source_name} API request failed with HTTP {status_code}."
    return f"{source_name} API request failed: {exc}"


def _batched(items: list, size: int):
    if size < 1:
        raise SystemExit("--batch-size must be at least 1.")
    for start in range(0, len(items), size):
        yield items[start : start + size]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nuclear-energy")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_rss = subparsers.add_parser("ingest-rss", help="Fetch configured RSS feeds and store documents.")
    ingest_rss.add_argument("--feed", action="append", help="RSS feed URL. May be repeated.")
    ingest_rss.add_argument("--limit", type=int, default=25, help="Maximum entries per feed.")
    ingest_rss.set_defaults(func=_ingest_rss)

    ingest_gdelt = subparsers.add_parser(
        "ingest-gdelt",
        help="Search the GDELT DOC API and store matching news documents.",
    )
    ingest_gdelt.add_argument("--query", default=DEFAULT_GDELT_QUERY, help="GDELT DOC search query.")
    ingest_gdelt.add_argument("--limit", type=int, default=25, help="Maximum documents to store.")
    ingest_gdelt.add_argument("--timespan", default="1week", help="GDELT timespan, such as 1day or 1week.")
    ingest_gdelt.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout for the API request.")
    ingest_gdelt.set_defaults(func=_ingest_gdelt)

    ingest_federal_register = subparsers.add_parser(
        "ingest-federal-register",
        help="Search the Federal Register API and store matching documents.",
    )
    ingest_federal_register.add_argument(
        "--query",
        default=DEFAULT_FEDERAL_REGISTER_QUERY,
        help="Federal Register search query.",
    )
    ingest_federal_register.add_argument("--limit", type=int, default=25, help="Maximum documents to store.")
    ingest_federal_register.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout for the API request.")
    ingest_federal_register.set_defaults(func=_ingest_federal_register)

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

    embed_chunks = subparsers.add_parser(
        "embed-chunks",
        help="Create OpenAI embeddings for stored document chunks.",
    )
    embed_chunks.add_argument("--limit", type=int, default=25, help="Maximum chunks to embed.")
    embed_chunks.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_EMBEDDING_BATCH_SIZE,
        help="Maximum chunks to send to OpenAI in one request.",
    )
    embed_chunks.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL, help="OpenAI embedding model.")
    embed_chunks.set_defaults(func=_embed_chunks)

    search_chunks = subparsers.add_parser(
        "search-chunks",
        help="Search embedded document chunks by meaning.",
    )
    search_chunks.add_argument("query", help="Natural-language search query.")
    search_chunks.add_argument("--limit", type=int, default=5, help="Maximum search results.")
    search_chunks.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL, help="OpenAI embedding model.")
    search_chunks.add_argument("--source-name", help="Only search chunks from this exact source name.")
    search_chunks.add_argument(
        "--preview-chars",
        type=int,
        default=360,
        help="Maximum characters to print for each result preview.",
    )
    search_chunks.set_defaults(func=_search_chunks)

    export_documents = subparsers.add_parser(
        "export-documents",
        help="Export stored documents to CSV or Markdown.",
    )
    export_documents.add_argument("--format", choices=["csv", "markdown"], default="csv", help="Export format.")
    export_documents.add_argument("--output", help="Output file path.")
    export_documents.add_argument("--limit", type=int, default=100, help="Maximum documents to export.")
    export_documents.add_argument("--source-name", help="Only export documents from this exact source name.")
    export_documents.add_argument(
        "--preview-chars",
        type=int,
        default=1200,
        help="Maximum content characters per exported document.",
    )
    export_documents.set_defaults(func=_export_documents)

    dashboard = subparsers.add_parser("dashboard", help="Open the Streamlit dashboard.")
    dashboard.add_argument("--address", default="127.0.0.1", help="Dashboard host address.")
    dashboard.add_argument("--port", type=int, default=8501, help="Dashboard port.")
    dashboard.set_defaults(func=_dashboard)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
