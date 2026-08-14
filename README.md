# Nuclear Energy

Nuclear energy intelligence ingestion and analysis pipeline.

The project currently has a Supabase/Postgres schema for nuclear reference data, public document ingestion, and a Streamlit dashboard for tracking nuclear-energy intelligence and electricity-system metrics.

## Current Pieces

- Supabase migrations for countries, reactors, plants, facilities, generation, safety events, and source documents.
- Python project skeleton under `src/nuclear_energy`.
- RSS ingestion CLI that normalizes feed entries and stores them in Postgres.
- Article extraction and chunking CLI that stores clean text in `document_chunks`.
- OpenAI embedding CLI that stores chunk vectors in `pgvector`.
- Semantic search CLI for finding relevant chunks by meaning.
- Public country electricity metrics from Ember, including nuclear generation, nuclear capacity, electricity demand, total generation, and net electricity imports/exports.
- Rule-based public transaction detection from stored documents, linked back to source articles and regulatory records.
- Official structured procurement feeds from USAspending.gov and EU TED, stored as transaction rows with source evidence documents.
- Streamlit dashboard for database status, energy-system metrics, transaction signals, keyword search, and exports.

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

You can also ingest from public APIs that do not require API keys.

```bash
nuclear-energy ingest-gdelt --limit 20
nuclear-energy ingest-federal-register --limit 20
nuclear-energy ingest-eur-lex --limit 20
```

Load public annual electricity-system data.

```bash
nuclear-energy ingest-energy --since-year 2000
```

Load official structured public procurement and award feeds.

```bash
nuclear-energy ingest-usaspending --limit 50
nuclear-energy ingest-eu-ted --limit 50
```

6. Extract and chunk stored articles.

```bash
nuclear-energy extract-documents --limit 20
```

Detect public transaction signals in stored documents.

```bash
nuclear-energy detect-transactions --limit 500
```

7. Embed stored chunks and try semantic search.

```bash
nuclear-energy embed-chunks --limit 20
nuclear-energy search-chunks "small modular reactor licensing" --limit 5
```

Open the local dashboard.

```bash
nuclear-energy dashboard
```

For Streamlit Community Cloud, use `streamlit_app.py` as the main file path.

Export stored documents.

```bash
nuclear-energy export-documents --format csv --output exports/documents.csv
nuclear-energy export-documents --format markdown --output exports/documents.md
```

## GitHub Actions

- `CI` runs the test suite on pushes and pull requests.
- `Public Source Ingest` can run manually or on its daily schedule. It skips itself unless the repository has a `DATABASE_URL` secret configured for a Postgres/Supabase database, using the same `postgresql+psycopg://...` format as local development.
- The Streamlit `Automation` tab can trigger `Public Source Ingest` when Streamlit secrets include:
  - `GITHUB_ACTIONS_TOKEN`: a GitHub fine-grained token for this repository with Actions read/write access.
  - `WORKFLOW_TRIGGER_PIN`: a private PIN required in the app before the workflow can be started.

## Tests

```bash
pytest
```
