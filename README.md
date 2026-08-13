# Nuclear Energy

Nuclear energy intelligence ingestion and analysis pipeline.

The project currently has a Supabase/Postgres schema for nuclear reference data and a Python ingestion foundation for RSS-backed source documents.

## Current Pieces

- Supabase migrations for countries, reactors, plants, facilities, generation, safety events, and source documents.
- Python project skeleton under `src/nuclear_energy`.
- RSS ingestion CLI that normalizes feed entries and stores them in Postgres.
- Article extraction and chunking CLI that stores clean text in `document_chunks`.
- Document-ingestion tables with room for future OpenAI embeddings through `pgvector`.

## Setup

1. Create a virtual environment.
2. Install the Python project.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

3. Copy `.env.example` to `.env.local` and fill in missing values.
4. Start or connect to the Supabase database.
5. Run an RSS ingestion pass.

```bash
nuclear-energy ingest-rss --limit 20
```

6. Extract and chunk stored articles.

```bash
nuclear-energy extract-documents --limit 20
```

## Tests

```bash
pytest
```
