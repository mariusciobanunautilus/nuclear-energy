set check_function_bodies = false;

create table public.nuclear_transactions (
  id uuid primary key default extensions.gen_random_uuid(),
  external_id text not null unique,
  document_id uuid not null references public.ingested_documents(id) on delete cascade,
  transaction_date timestamptz,
  country_iso_code text check (country_iso_code is null or country_iso_code ~ '^[A-Z]{3}$'),
  country_name text,
  plant_name text,
  project_name text,
  transaction_type text not null check (
    transaction_type in (
      'contract_award',
      'financing',
      'construction_refurbishment',
      'fuel_supply',
      'merger_acquisition'
    )
  ),
  stage text not null default 'detected' check (
    stage in ('detected', 'confirmed_award', 'regulatory_filing', 'company_announcement', 'news_reported')
  ),
  title text not null check (length(btrim(title)) > 0),
  summary text not null check (length(btrim(summary)) > 0),
  source_name text not null check (length(btrim(source_name)) > 0),
  source_url text not null check (source_url ~* '^https?://'),
  amount_text text,
  amount numeric(18,2) check (amount is null or amount >= 0),
  currency text check (currency is null or currency ~ '^[A-Z]{3}$'),
  counterparties jsonb not null default '[]'::jsonb,
  matched_terms jsonb not null default '[]'::jsonb,
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint nuclear_transaction_has_country_or_plant check (
    country_iso_code is not null
    or plant_name is not null
  )
);

create trigger nuclear_transactions_set_updated_at
  before update on public.nuclear_transactions
  for each row execute function public.set_updated_at();

create index nuclear_transactions_country_date_idx
  on public.nuclear_transactions (country_iso_code, transaction_date desc);

create index nuclear_transactions_date_idx
  on public.nuclear_transactions (transaction_date desc)
  where transaction_date is not null;

create index nuclear_transactions_type_idx
  on public.nuclear_transactions (transaction_type);

create index nuclear_transactions_amount_idx
  on public.nuclear_transactions (amount desc)
  where amount is not null;

alter table public.nuclear_transactions enable row level security;

create policy "nuclear transactions are publicly readable"
  on public.nuclear_transactions for select
  to anon, authenticated
  using (true);

grant select on public.nuclear_transactions to anon, authenticated;
grant all on public.nuclear_transactions to service_role;
