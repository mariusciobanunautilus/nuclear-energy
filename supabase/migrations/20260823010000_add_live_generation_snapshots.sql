set check_function_bodies = false;

create table public.live_generation_snapshots (
  id uuid primary key default extensions.gen_random_uuid(),
  country_iso_code text not null check (country_iso_code ~ '^[A-Z]{3}$'),
  country_name text not null check (length(btrim(country_name)) > 0),
  observed_at timestamptz not null,
  demand_mw integer,
  production_mw integer,
  net_import_export_mw integer,
  nuclear_mw integer,
  wind_mw integer,
  hydro_mw integer,
  hydrocarbons_mw integer,
  coal_mw integer,
  solar_mw integer,
  biomass_mw integer,
  storage_mw integer,
  source_name text not null check (length(btrim(source_name)) > 0),
  source_url text not null check (source_url ~* '^https?://'),
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (country_iso_code, observed_at, source_name)
);

create trigger live_generation_snapshots_set_updated_at
  before update on public.live_generation_snapshots
  for each row execute function public.set_updated_at();

create index live_generation_snapshots_country_observed_idx
  on public.live_generation_snapshots (country_iso_code, observed_at desc);

create index live_generation_snapshots_source_observed_idx
  on public.live_generation_snapshots (source_name, observed_at desc);

alter table public.live_generation_snapshots enable row level security;

create policy "live generation snapshots are publicly readable"
  on public.live_generation_snapshots for select
  to anon, authenticated
  using (true);

grant select on public.live_generation_snapshots to anon, authenticated;
grant all on public.live_generation_snapshots to service_role;
