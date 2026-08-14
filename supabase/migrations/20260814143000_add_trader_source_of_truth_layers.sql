set check_function_bodies = false;

alter table public.ingestion_runs
  add column if not exists source_tier text not null default 'unclassified'
  check (
    source_tier in (
      'tier_1_official_structured',
      'tier_2_official_document',
      'tier_3_company_statement',
      'tier_4_reported_media',
      'tier_5_discovery_feed',
      'unclassified'
    )
  );

alter table public.ingested_documents
  add column if not exists source_tier text not null default 'unclassified'
  check (
    source_tier in (
      'tier_1_official_structured',
      'tier_2_official_document',
      'tier_3_company_statement',
      'tier_4_reported_media',
      'tier_5_discovery_feed',
      'unclassified'
    )
  ),
  add column if not exists ingested_at timestamptz not null default now(),
  add column if not exists last_seen_at timestamptz not null default now();

create table public.entities (
  id uuid primary key default extensions.gen_random_uuid(),
  canonical_name text not null check (length(btrim(canonical_name)) > 0),
  entity_type text not null default 'unknown' check (
    entity_type in (
      'company',
      'government_agency',
      'regulator',
      'utility',
      'vendor',
      'country',
      'unknown'
    )
  ),
  country_iso_code text check (country_iso_code is null or country_iso_code ~ '^[A-Z]{3}$'),
  source_tier text not null default 'unclassified',
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (canonical_name)
);

create table public.entity_aliases (
  id uuid primary key default extensions.gen_random_uuid(),
  entity_id uuid not null references public.entities(id) on delete cascade,
  alias text not null check (length(btrim(alias)) > 0),
  created_at timestamptz not null default now(),
  unique (entity_id, alias),
  unique (alias)
);

create table public.projects (
  id uuid primary key default extensions.gen_random_uuid(),
  canonical_name text not null check (length(btrim(canonical_name)) > 0),
  project_type text not null default 'unknown' check (
    project_type in (
      'plant',
      'reactor',
      'smr',
      'fuel_facility',
      'mine',
      'life_extension',
      'waste',
      'unknown'
    )
  ),
  country_iso_code text check (country_iso_code is null or country_iso_code ~ '^[A-Z]{3}$'),
  country_name text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (canonical_name, country_iso_code)
);

create table public.project_aliases (
  id uuid primary key default extensions.gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  alias text not null check (length(btrim(alias)) > 0),
  created_at timestamptz not null default now(),
  unique (project_id, alias)
);

create table public.nuclear_events (
  id uuid primary key default extensions.gen_random_uuid(),
  external_id text not null unique,
  source_document_id uuid references public.ingested_documents(id) on delete set null,
  event_type text not null check (
    event_type in (
      'public_tender',
      'contract_award',
      'financing',
      'subsidy_or_grant',
      'license_application',
      'license_approval',
      'construction_start',
      'construction_refurbishment',
      'delay_or_cost_overrun',
      'restart',
      'life_extension',
      'outage',
      'fuel_supply',
      'sanction_or_export_control',
      'policy_change',
      'm_and_a',
      'merger_acquisition',
      'reported_development'
    )
  ),
  event_status text not null default 'detected' check (
    event_status in (
      'confirmed',
      'proposed',
      'public_tender',
      'reported',
      'detected',
      'needs_review'
    )
  ),
  source_tier text not null default 'unclassified',
  event_date timestamptz,
  country_iso_code text check (country_iso_code is null or country_iso_code ~ '^[A-Z]{3}$'),
  country_name text,
  project_name text,
  title text not null check (length(btrim(title)) > 0),
  summary text not null check (length(btrim(summary)) > 0),
  amount numeric(18,2) check (amount is null or amount >= 0),
  amount_text text,
  currency text check (currency is null or currency ~ '^[A-Z]{3}$'),
  materiality_flags jsonb not null default '[]'::jsonb,
  themes jsonb not null default '[]'::jsonb,
  source_confidence numeric(4,3) not null default 0 check (source_confidence between 0 and 1),
  review_status text not null default 'unreviewed' check (
    review_status in ('unreviewed', 'reviewed', 'important', 'irrelevant', 'duplicate', 'corrected')
  ),
  review_note text,
  reviewed_at timestamptz,
  duplicate_of_event_id uuid references public.nuclear_events(id) on delete set null,
  raw_payload jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.event_entities (
  event_id uuid not null references public.nuclear_events(id) on delete cascade,
  entity_id uuid not null references public.entities(id) on delete cascade,
  role text not null default 'mentioned' check (
    role in ('buyer', 'seller', 'recipient', 'awarding_agency', 'regulator', 'operator', 'owner', 'mentioned')
  ),
  created_at timestamptz not null default now(),
  primary key (event_id, entity_id, role)
);

create table public.event_projects (
  event_id uuid not null references public.nuclear_events(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  role text not null default 'related_project' check (
    role in ('related_project', 'plant', 'facility', 'license_target')
  ),
  created_at timestamptz not null default now(),
  primary key (event_id, project_id, role)
);

create table public.event_evidence (
  id uuid primary key default extensions.gen_random_uuid(),
  event_id uuid not null references public.nuclear_events(id) on delete cascade,
  document_id uuid references public.ingested_documents(id) on delete set null,
  evidence_kind text not null default 'source_excerpt' check (
    evidence_kind in ('source_excerpt', 'transaction_summary', 'raw_payload', 'human_note')
  ),
  source_name text not null check (length(btrim(source_name)) > 0),
  source_url text not null check (source_url ~* '^https?://'),
  source_tier text not null default 'unclassified',
  published_at timestamptz,
  snippet text not null check (length(btrim(snippet)) > 0),
  extracted_at timestamptz not null default now(),
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (event_id, document_id, evidence_kind)
);

create table public.event_reviews (
  id uuid primary key default extensions.gen_random_uuid(),
  event_id uuid not null references public.nuclear_events(id) on delete cascade,
  review_status text not null check (
    review_status in ('reviewed', 'important', 'irrelevant', 'duplicate', 'corrected')
  ),
  previous_status text check (
    previous_status is null
    or previous_status in ('unreviewed', 'reviewed', 'important', 'irrelevant', 'duplicate', 'corrected')
  ),
  review_action text not null default 'status_update' check (
    review_action in ('status_update', 'mark_important', 'mark_irrelevant', 'mark_duplicate', 'correction')
  ),
  duplicate_of_event_id uuid references public.nuclear_events(id) on delete set null,
  patch_payload jsonb not null default '{}'::jsonb,
  note text,
  reviewer text,
  created_at timestamptz not null default now()
);

create trigger entities_set_updated_at
  before update on public.entities
  for each row execute function public.set_updated_at();

create trigger projects_set_updated_at
  before update on public.projects
  for each row execute function public.set_updated_at();

create trigger nuclear_events_set_updated_at
  before update on public.nuclear_events
  for each row execute function public.set_updated_at();

create index ingestion_runs_tier_finished_idx
  on public.ingestion_runs (source_tier, finished_at desc)
  where finished_at is not null;

create index ingested_documents_tier_seen_idx
  on public.ingested_documents (source_tier, last_seen_at desc);

create index entities_country_idx
  on public.entities (country_iso_code)
  where country_iso_code is not null;

create index entity_aliases_alias_idx
  on public.entity_aliases (alias);

create index projects_country_idx
  on public.projects (country_iso_code)
  where country_iso_code is not null;

create index nuclear_events_date_idx
  on public.nuclear_events (event_date desc)
  where event_date is not null;

create index nuclear_events_country_date_idx
  on public.nuclear_events (country_iso_code, event_date desc)
  where country_iso_code is not null;

create index nuclear_events_type_date_idx
  on public.nuclear_events (event_type, event_date desc);

create index nuclear_events_review_status_idx
  on public.nuclear_events (review_status, event_date desc);

create index nuclear_events_duplicate_of_idx
  on public.nuclear_events (duplicate_of_event_id)
  where duplicate_of_event_id is not null;

create index nuclear_events_source_tier_idx
  on public.nuclear_events (source_tier, event_date desc);

create index nuclear_events_materiality_flags_idx
  on public.nuclear_events using gin (materiality_flags);

create index nuclear_events_themes_idx
  on public.nuclear_events using gin (themes);

create index event_evidence_event_idx
  on public.event_evidence (event_id);

create index event_reviews_event_created_idx
  on public.event_reviews (event_id, created_at desc);

alter table public.entities enable row level security;
alter table public.entity_aliases enable row level security;
alter table public.projects enable row level security;
alter table public.project_aliases enable row level security;
alter table public.nuclear_events enable row level security;
alter table public.event_entities enable row level security;
alter table public.event_projects enable row level security;
alter table public.event_evidence enable row level security;
alter table public.event_reviews enable row level security;

create policy "entities are publicly readable"
  on public.entities for select
  to anon, authenticated
  using (true);

create policy "entity aliases are publicly readable"
  on public.entity_aliases for select
  to anon, authenticated
  using (true);

create policy "projects are publicly readable"
  on public.projects for select
  to anon, authenticated
  using (true);

create policy "project aliases are publicly readable"
  on public.project_aliases for select
  to anon, authenticated
  using (true);

create policy "nuclear events are publicly readable"
  on public.nuclear_events for select
  to anon, authenticated
  using (true);

create policy "event entities are publicly readable"
  on public.event_entities for select
  to anon, authenticated
  using (true);

create policy "event projects are publicly readable"
  on public.event_projects for select
  to anon, authenticated
  using (true);

create policy "event evidence is publicly readable"
  on public.event_evidence for select
  to anon, authenticated
  using (true);

grant select on
  public.entities,
  public.entity_aliases,
  public.projects,
  public.project_aliases,
  public.nuclear_events,
  public.event_entities,
  public.event_projects,
  public.event_evidence
to anon, authenticated;

grant all on
  public.entities,
  public.entity_aliases,
  public.projects,
  public.project_aliases,
  public.nuclear_events,
  public.event_entities,
  public.event_projects,
  public.event_evidence,
  public.event_reviews
to service_role;
