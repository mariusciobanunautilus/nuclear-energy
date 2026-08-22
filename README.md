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
- Source-backed nuclear event detection for policy, licensing, construction, outage, restart, fuel-cycle, delay, and supply-risk developments.
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
5. Run an RSS ingestion pass. By default, this pulls a curated public feed set covering
   World Nuclear News, ANS Nuclear Newswire, IAEA top news, NRC news releases, and NRC plant status.
   Override `RSS_FEEDS` when you want a narrower or custom list.

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

Detect broader source-backed nuclear events in stored documents.

```bash
nuclear-energy detect-events --limit 500
```

Refresh normalized event rows from stored transaction evidence.

```bash
nuclear-energy sync-events
```

Refresh entity and project links for normalized events.

```bash
nuclear-energy sync-relationships
```

Check whether the ingestion flood is measurable and where processing is backed up.

```bash
nuclear-energy completeness-report
```

Repair source trust tiers on existing documents, events, and evidence after migrations or older ingests.

```bash
nuclear-energy repair-source-tiers
```

The dashboard Review Queue turns normalized events into a trader-maintained source of truth. It ranks items by review urgency, shows source evidence, records confirmations, promotes important events into the Daily Tape, marks noise, links duplicates, and stores correction history instead of silently overwriting facts.

Trader watchlists and public RSS feeds have built-in defaults and can be overridden with comma-separated environment values.

```toml
WATCHLIST_ENTITIES = "Westinghouse Electric Company,Cameco,Centrus Energy,Orano,Framatome,Urenco,Kazatomprom,Rosatom"
WATCHLIST_PROJECTS = "Cernavoda,Dukovany,Sizewell C,Hinkley Point C,Vogtle,Bruce"
WATCHLIST_COUNTRIES = "USA,CAN,FRA,GBR,ROU,CZE,POL,BGR,UKR,RUS,CHN,JPN,KOR,KAZ"
WATCHLIST_THEMES = "fuel_cycle,policy,regulation,project_stage,construction,operations,project_risk,supply_risk"
RSS_FEEDS = "https://world-nuclear-news.org/rss,https://www.ans.org/news/feed/,https://www.iaea.org/feeds/topnews,https://www.nrc.gov/public-involve/rss?feed=news,https://www.nrc.gov/public-involve/rss?feed=plant-status"
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
- The workflow also refreshes detected events, transaction-derived events, and entity/project links. If `OPENAI_API_KEY` is configured, it embeds new chunks for semantic search; otherwise it skips embeddings and still refreshes the source-of-truth tables.
- The Streamlit `Automation` tab can trigger `Public Source Ingest` when Streamlit secrets include:
  - `GITHUB_ACTIONS_TOKEN`: a GitHub fine-grained token for this repository with Actions read/write access.
  - `WORKFLOW_TRIGGER_PIN`: a private PIN required in the app before the workflow can be started.

Streamlit secrets example:

```toml
DATABASE_URL = "postgresql+psycopg://..."
OPENAI_API_KEY = "sk-proj-..."
GITHUB_ACTIONS_TOKEN = "github_pat_..."
WORKFLOW_TRIGGER_PIN = "choose-a-private-pin"
```

## Tests

```bash
pytest
```
