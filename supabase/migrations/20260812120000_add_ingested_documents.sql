set check_function_bodies = false;

create extension if not exists vector with schema extensions;

create type public.document_source_kind as enum (
  'rss',
  'gdelt',
  'eur_lex',
  'congress',
  'federal_register',
  'regulations_gov'
);

create table public.ingestion_runs (
  id uuid primary key default extensions.gen_random_uuid(),
  source_kind public.document_source_kind not null,
  source_name text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running' check (status in ('running', 'succeeded', 'failed')),
  documents_seen integer not null default 0 check (documents_seen >= 0),
  documents_stored integer not null default 0 check (documents_stored >= 0),
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.ingested_documents (
  id uuid primary key default extensions.gen_random_uuid(),
  source_kind public.document_source_kind not null,
  source_name text not null,
  external_id text not null,
  title text not null,
  url text not null check (url ~* '^https?://'),
  published_at timestamptz,
  summary text,
  content text,
  authors jsonb not null default '[]'::jsonb,
  tags jsonb not null default '[]'::jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source_kind, external_id),
  unique (url)
);

create table public.document_chunks (
  id uuid primary key default extensions.gen_random_uuid(),
  document_id uuid not null references public.ingested_documents(id) on delete cascade,
  chunk_index integer not null check (chunk_index >= 0),
  content text not null,
  token_count integer check (token_count is null or token_count > 0),
  embedding extensions.vector(1536),
  embedding_model text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (document_id, chunk_index)
);

create trigger ingestion_runs_set_updated_at
  before update on public.ingestion_runs
  for each row execute function public.set_updated_at();

create trigger ingested_documents_set_updated_at
  before update on public.ingested_documents
  for each row execute function public.set_updated_at();

create trigger document_chunks_set_updated_at
  before update on public.document_chunks
  for each row execute function public.set_updated_at();

create index ingestion_runs_source_started_idx
  on public.ingestion_runs (source_kind, started_at desc);

create index ingested_documents_source_published_idx
  on public.ingested_documents (source_kind, published_at desc);

create index ingested_documents_published_idx
  on public.ingested_documents (published_at desc)
  where published_at is not null;

create index ingested_documents_tags_idx
  on public.ingested_documents using gin (tags);

create index document_chunks_document_idx
  on public.document_chunks (document_id, chunk_index);

create index document_chunks_embedding_idx
  on public.document_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100)
  where embedding is not null;

alter table public.ingestion_runs enable row level security;
alter table public.ingested_documents enable row level security;
alter table public.document_chunks enable row level security;

create policy "ingestion runs are publicly readable"
  on public.ingestion_runs for select
  to anon, authenticated
  using (true);

create policy "ingested documents are publicly readable"
  on public.ingested_documents for select
  to anon, authenticated
  using (true);

create policy "document chunks are publicly readable"
  on public.document_chunks for select
  to anon, authenticated
  using (true);

grant select on
  public.ingestion_runs,
  public.ingested_documents,
  public.document_chunks
to anon, authenticated;

grant all on
  public.ingestion_runs,
  public.ingested_documents,
  public.document_chunks
to service_role;
