set check_function_bodies = false;

create table public.country_energy_years (
  id uuid primary key default extensions.gen_random_uuid(),
  iso_code text not null check (iso_code ~ '^[A-Z]{3}$'),
  country_name text not null check (length(btrim(country_name)) > 0),
  year integer not null check (year between 1950 and 2100),
  nuclear_generation_twh numeric(12,3) check (nuclear_generation_twh is null or nuclear_generation_twh >= 0),
  nuclear_share_electricity_percent numeric(6,3) check (
    nuclear_share_electricity_percent is null
    or nuclear_share_electricity_percent between 0 and 100
  ),
  nuclear_capacity_gw numeric(12,3) check (nuclear_capacity_gw is null or nuclear_capacity_gw >= 0),
  electricity_generation_twh numeric(12,3) check (
    electricity_generation_twh is null
    or electricity_generation_twh >= 0
  ),
  electricity_demand_twh numeric(12,3) check (
    electricity_demand_twh is null
    or electricity_demand_twh >= 0
  ),
  net_electricity_imports_twh numeric(12,3),
  fossil_generation_twh numeric(12,3) check (fossil_generation_twh is null or fossil_generation_twh >= 0),
  renewables_generation_twh numeric(12,3) check (
    renewables_generation_twh is null
    or renewables_generation_twh >= 0
  ),
  clean_generation_twh numeric(12,3) check (clean_generation_twh is null or clean_generation_twh >= 0),
  source_name text not null check (length(btrim(source_name)) > 0),
  source_url text not null check (source_url ~* '^https?://'),
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (iso_code, year)
);

create trigger country_energy_years_set_updated_at
  before update on public.country_energy_years
  for each row execute function public.set_updated_at();

create index country_energy_years_iso_year_idx
  on public.country_energy_years (iso_code, year desc);

create index country_energy_years_latest_idx
  on public.country_energy_years (year desc);

create index country_energy_years_nuclear_generation_idx
  on public.country_energy_years (nuclear_generation_twh desc)
  where nuclear_generation_twh is not null;

alter table public.country_energy_years enable row level security;

create policy "country energy years are publicly readable"
  on public.country_energy_years for select
  to anon, authenticated
  using (true);

grant select on public.country_energy_years to anon, authenticated;
grant all on public.country_energy_years to service_role;
