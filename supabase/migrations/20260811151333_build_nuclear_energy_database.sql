set check_function_bodies = false;

create extension if not exists pgcrypto with schema extensions;

create type public.reactor_status as enum (
  'planned',
  'under_construction',
  'operational',
  'suspended',
  'shutdown',
  'decommissioning',
  'decommissioned'
);

create type public.facility_type as enum (
  'uranium_mine',
  'conversion',
  'enrichment',
  'fuel_fabrication',
  'research',
  'storage',
  'reprocessing',
  'waste_repository'
);

create type public.incident_severity as enum (
  'info',
  'low',
  'medium',
  'high',
  'severe'
);

create table public.countries (
  id uuid primary key default extensions.gen_random_uuid(),
  iso2 text not null unique check (iso2 ~ '^[A-Z]{2}$'),
  iso3 text not null unique check (iso3 ~ '^[A-Z]{3}$'),
  name text not null unique,
  region text not null,
  has_commercial_nuclear boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.reactor_technologies (
  id uuid primary key default extensions.gen_random_uuid(),
  code text not null unique,
  name text not null,
  moderator text,
  coolant text,
  neutron_spectrum text not null default 'thermal',
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.source_documents (
  id uuid primary key default extensions.gen_random_uuid(),
  title text not null,
  publisher text,
  url text,
  published_on date,
  accessed_on date not null default current_date,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint source_documents_url_format check (
    url is null or url ~* '^https?://'
  )
);

create table public.power_plants (
  id uuid primary key default extensions.gen_random_uuid(),
  country_id uuid not null references public.countries(id) on delete restrict,
  name text not null,
  operator text,
  owner text,
  locality text,
  latitude numeric(9,6) check (latitude between -90 and 90),
  longitude numeric(9,6) check (longitude between -180 and 180),
  source_id uuid references public.source_documents(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (country_id, name)
);

create table public.reactors (
  id uuid primary key default extensions.gen_random_uuid(),
  plant_id uuid not null references public.power_plants(id) on delete cascade,
  technology_id uuid references public.reactor_technologies(id) on delete set null,
  name text not null,
  status public.reactor_status not null,
  net_capacity_mwe integer check (net_capacity_mwe > 0),
  gross_capacity_mwe integer check (gross_capacity_mwe is null or gross_capacity_mwe > 0),
  construction_started_on date,
  grid_connected_on date,
  commercial_operation_on date,
  shutdown_on date,
  source_id uuid references public.source_documents(id) on delete set null,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (plant_id, name),
  constraint reactor_date_order check (
    (construction_started_on is null or grid_connected_on is null or construction_started_on <= grid_connected_on)
    and (grid_connected_on is null or commercial_operation_on is null or grid_connected_on <= commercial_operation_on)
    and (commercial_operation_on is null or shutdown_on is null or commercial_operation_on <= shutdown_on)
  )
);

create table public.country_generation_years (
  id uuid primary key default extensions.gen_random_uuid(),
  country_id uuid not null references public.countries(id) on delete cascade,
  year integer not null check (year between 1950 and 2100),
  nuclear_generation_twh numeric(10,3) check (nuclear_generation_twh >= 0),
  nuclear_share_percent numeric(5,2) check (nuclear_share_percent between 0 and 100),
  reactors_operable integer check (reactors_operable >= 0),
  source_id uuid references public.source_documents(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (country_id, year)
);

create table public.fuel_cycle_facilities (
  id uuid primary key default extensions.gen_random_uuid(),
  country_id uuid not null references public.countries(id) on delete restrict,
  type public.facility_type not null,
  name text not null,
  operator text,
  status text not null default 'unknown',
  locality text,
  annual_capacity text,
  source_id uuid references public.source_documents(id) on delete set null,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (country_id, type, name)
);

create table public.safety_events (
  id uuid primary key default extensions.gen_random_uuid(),
  reactor_id uuid references public.reactors(id) on delete set null,
  country_id uuid references public.countries(id) on delete set null,
  event_date date not null,
  title text not null,
  severity public.incident_severity not null default 'info',
  ines_level integer check (ines_level between 0 and 7),
  summary text,
  source_id uuid references public.source_documents(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint safety_event_has_location check (reactor_id is not null or country_id is not null)
);

create table public.reactor_sources (
  reactor_id uuid not null references public.reactors(id) on delete cascade,
  source_id uuid not null references public.source_documents(id) on delete cascade,
  note text,
  created_at timestamptz not null default now(),
  primary key (reactor_id, source_id)
);

create function public.set_updated_at()
  returns trigger
  language plpgsql
  set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger countries_set_updated_at
  before update on public.countries
  for each row execute function public.set_updated_at();

create trigger reactor_technologies_set_updated_at
  before update on public.reactor_technologies
  for each row execute function public.set_updated_at();

create trigger source_documents_set_updated_at
  before update on public.source_documents
  for each row execute function public.set_updated_at();

create trigger power_plants_set_updated_at
  before update on public.power_plants
  for each row execute function public.set_updated_at();

create trigger reactors_set_updated_at
  before update on public.reactors
  for each row execute function public.set_updated_at();

create trigger country_generation_years_set_updated_at
  before update on public.country_generation_years
  for each row execute function public.set_updated_at();

create trigger fuel_cycle_facilities_set_updated_at
  before update on public.fuel_cycle_facilities
  for each row execute function public.set_updated_at();

create trigger safety_events_set_updated_at
  before update on public.safety_events
  for each row execute function public.set_updated_at();

create index countries_region_idx on public.countries (region);
create index power_plants_country_id_idx on public.power_plants (country_id);
create index reactors_plant_id_idx on public.reactors (plant_id);
create index reactors_status_idx on public.reactors (status);
create index reactors_technology_id_idx on public.reactors (technology_id);
create index country_generation_years_country_year_idx on public.country_generation_years (country_id, year desc);
create index fuel_cycle_facilities_country_type_idx on public.fuel_cycle_facilities (country_id, type);
create index safety_events_event_date_idx on public.safety_events (event_date desc);
create index safety_events_country_id_idx on public.safety_events (country_id);
create index safety_events_reactor_id_idx on public.safety_events (reactor_id);

alter table public.countries enable row level security;
alter table public.reactor_technologies enable row level security;
alter table public.source_documents enable row level security;
alter table public.power_plants enable row level security;
alter table public.reactors enable row level security;
alter table public.country_generation_years enable row level security;
alter table public.fuel_cycle_facilities enable row level security;
alter table public.safety_events enable row level security;
alter table public.reactor_sources enable row level security;

create policy "countries are publicly readable"
  on public.countries for select
  to anon, authenticated
  using (true);

create policy "reactor technologies are publicly readable"
  on public.reactor_technologies for select
  to anon, authenticated
  using (true);

create policy "source documents are publicly readable"
  on public.source_documents for select
  to anon, authenticated
  using (true);

create policy "power plants are publicly readable"
  on public.power_plants for select
  to anon, authenticated
  using (true);

create policy "reactors are publicly readable"
  on public.reactors for select
  to anon, authenticated
  using (true);

create policy "country generation years are publicly readable"
  on public.country_generation_years for select
  to anon, authenticated
  using (true);

create policy "fuel cycle facilities are publicly readable"
  on public.fuel_cycle_facilities for select
  to anon, authenticated
  using (true);

create policy "safety events are publicly readable"
  on public.safety_events for select
  to anon, authenticated
  using (true);

create policy "reactor sources are publicly readable"
  on public.reactor_sources for select
  to anon, authenticated
  using (true);

grant usage on schema public to anon, authenticated;
grant select on
  public.countries,
  public.reactor_technologies,
  public.source_documents,
  public.power_plants,
  public.reactors,
  public.country_generation_years,
  public.fuel_cycle_facilities,
  public.safety_events,
  public.reactor_sources
to anon, authenticated;

grant all on
  public.countries,
  public.reactor_technologies,
  public.source_documents,
  public.power_plants,
  public.reactors,
  public.country_generation_years,
  public.fuel_cycle_facilities,
  public.safety_events,
  public.reactor_sources
to service_role;

grant execute on function public.set_updated_at() to service_role;

revoke execute on function public.set_updated_at() from public;
revoke execute on function public.set_updated_at() from anon;
revoke execute on function public.set_updated_at() from authenticated;

insert into public.countries (iso2, iso3, name, region, has_commercial_nuclear)
values
  ('CA', 'CAN', 'Canada', 'North America', true),
  ('CN', 'CHN', 'China', 'Asia', true),
  ('FI', 'FIN', 'Finland', 'Europe', true),
  ('FR', 'FRA', 'France', 'Europe', true),
  ('JP', 'JPN', 'Japan', 'Asia', true),
  ('KR', 'KOR', 'South Korea', 'Asia', true),
  ('RO', 'ROU', 'Romania', 'Europe', true),
  ('UA', 'UKR', 'Ukraine', 'Europe', true),
  ('US', 'USA', 'United States', 'North America', true);

insert into public.reactor_technologies (code, name, moderator, coolant, neutron_spectrum, notes)
values
  ('PWR', 'Pressurized water reactor', 'Light water', 'Light water', 'thermal', 'The most common commercial power-reactor family.'),
  ('BWR', 'Boiling water reactor', 'Light water', 'Light water', 'thermal', 'Steam is generated directly in the reactor vessel.'),
  ('PHWR', 'Pressurized heavy water reactor', 'Heavy water', 'Heavy water', 'thermal', 'Often associated with CANDU-style designs.'),
  ('GCR', 'Gas-cooled reactor', 'Graphite', 'Carbon dioxide or helium', 'thermal', 'Includes several historic graphite-moderated designs.'),
  ('FBR', 'Fast breeder reactor', null, 'Liquid metal', 'fast', 'Fast-spectrum designs can convert fertile material into fissile fuel.');

insert into public.source_documents (title, publisher, url, notes)
values
  ('Power Reactor Information System', 'International Atomic Energy Agency', 'https://pris.iaea.org/', 'Canonical public reference for reactor-unit records.'),
  ('World Nuclear Performance Report', 'World Nuclear Association', 'https://world-nuclear.org/', 'Reference for global generation and performance context.'),
  ('Nuclear Power in the World Today', 'World Nuclear Association', 'https://world-nuclear.org/information-library/current-and-future-generation/nuclear-power-in-the-world-today', 'Country and technology overview reference.');

with
  src as (
    select id from public.source_documents where title = 'Power Reactor Information System'
  ),
  plants as (
    insert into public.power_plants (country_id, name, operator, locality, latitude, longitude, source_id)
    select c.id, v.name, v.operator, v.locality, v.latitude, v.longitude, src.id
    from (
      values
        ('USA', 'Watts Bar', 'Tennessee Valley Authority', 'Tennessee', 35.602000, -84.789000),
        ('FRA', 'Flamanville', 'EDF', 'Normandy', 49.536000, -1.882000),
        ('FIN', 'Olkiluoto', 'Teollisuuden Voima Oyj', 'Eurajoki', 61.237000, 21.440000),
        ('ROU', 'Cernavoda', 'Societatea Nationala Nuclearelectrica', 'Cernavoda', 44.322000, 28.057000),
        ('CAN', 'Bruce', 'Bruce Power', 'Ontario', 44.325000, -81.599000),
        ('JPN', 'Kashiwazaki-Kariwa', 'Tokyo Electric Power Company', 'Niigata', 37.429000, 138.595000)
    ) as v(country_iso3, name, operator, locality, latitude, longitude)
    join public.countries c on c.iso3 = v.country_iso3
    cross join src
    returning id, name
  )
insert into public.reactors (
  plant_id,
  technology_id,
  name,
  status,
  net_capacity_mwe,
  construction_started_on,
  grid_connected_on,
  commercial_operation_on,
  source_id,
  notes
)
select p.id, rt.id, v.name, v.status::public.reactor_status, v.net_capacity_mwe,
       v.construction_started_on::date, v.grid_connected_on::date, v.commercial_operation_on::date,
       src.id, v.notes
from (
  values
    ('Watts Bar', 'PWR', 'Watts Bar 1', 'operational', 1211, '1973-01-20', '1996-02-06', '1996-05-27', null),
    ('Watts Bar', 'PWR', 'Watts Bar 2', 'operational', 1165, '1973-09-01', '2016-06-03', '2016-10-19', null),
    ('Flamanville', 'PWR', 'Flamanville 3', 'operational', 1600, '2007-12-03', '2024-12-21', null, 'European Pressurized Reactor unit.'),
    ('Olkiluoto', 'PWR', 'Olkiluoto 3', 'operational', 1600, '2005-08-12', '2022-03-12', '2023-04-16', 'European Pressurized Reactor unit.'),
    ('Cernavoda', 'PHWR', 'Cernavoda 1', 'operational', 650, '1982-07-01', '1996-07-11', '1996-12-02', 'CANDU 6 unit.'),
    ('Cernavoda', 'PHWR', 'Cernavoda 2', 'operational', 650, '1983-07-01', '2007-08-07', '2007-10-05', 'CANDU 6 unit.'),
    ('Bruce', 'PHWR', 'Bruce A 1', 'operational', 769, '1971-06-01', '1977-01-14', '1977-09-01', 'CANDU unit.'),
    ('Kashiwazaki-Kariwa', 'BWR', 'Kashiwazaki-Kariwa 6', 'suspended', 1315, '1991-11-03', '1996-01-29', '1996-11-07', 'Advanced boiling water reactor.')
) as v(plant_name, technology_code, name, status, net_capacity_mwe, construction_started_on, grid_connected_on, commercial_operation_on, notes)
join plants p on p.name = v.plant_name
join public.reactor_technologies rt on rt.code = v.technology_code
cross join src;

with wna as (
  select id from public.source_documents where title = 'World Nuclear Performance Report'
)
insert into public.country_generation_years (country_id, year, nuclear_generation_twh, nuclear_share_percent, reactors_operable, source_id)
select c.id, v.year, v.nuclear_generation_twh, v.nuclear_share_percent, v.reactors_operable, wna.id
from (
  values
    ('USA', 2023, 775.000, 18.60, 93),
    ('FRA', 2023, 338.000, 64.80, 56),
    ('CHN', 2023, 433.000, 4.90, 55),
    ('KOR', 2023, 172.000, 30.70, 25),
    ('CAN', 2023, 89.000, 14.30, 19),
    ('JPN', 2023, 77.000, 7.60, 12),
    ('FIN', 2023, 34.000, 41.00, 5),
    ('ROU', 2023, 10.000, 19.80, 2)
) as v(country_iso3, year, nuclear_generation_twh, nuclear_share_percent, reactors_operable)
join public.countries c on c.iso3 = v.country_iso3
cross join wna;

with src as (
  select id from public.source_documents where title = 'Nuclear Power in the World Today'
)
insert into public.fuel_cycle_facilities (country_id, type, name, operator, status, locality, annual_capacity, source_id, notes)
select c.id, v.type::public.facility_type, v.name, v.operator, v.status, v.locality, v.annual_capacity, src.id, v.notes
from (
  values
    ('CAN', 'uranium_mine', 'Cigar Lake', 'Cameco', 'operational', 'Saskatchewan', null, 'High-grade uranium mine.'),
    ('FRA', 'reprocessing', 'La Hague', 'Orano', 'operational', 'Normandy', null, 'Spent fuel reprocessing complex.'),
    ('USA', 'waste_repository', 'Waste Isolation Pilot Plant', 'U.S. Department of Energy', 'operational', 'New Mexico', null, 'Geologic repository for defense transuranic waste.'),
    ('ROU', 'fuel_fabrication', 'Pitesti Nuclear Fuel Plant', 'Nuclearelectrica', 'operational', 'Mioveni', null, 'CANDU fuel fabrication.')
) as v(country_iso3, type, name, operator, status, locality, annual_capacity, notes)
join public.countries c on c.iso3 = v.country_iso3
cross join src;

with src as (
  select id from public.source_documents where title = 'Power Reactor Information System'
)
insert into public.safety_events (country_id, event_date, title, severity, ines_level, summary, source_id)
select c.id, v.event_date::date, v.title, v.severity::public.incident_severity, v.ines_level, v.summary, src.id
from (
  values
    ('USA', '1979-03-28', 'Three Mile Island Unit 2 accident', 'high', 5, 'Partial core melt at a pressurized water reactor in Pennsylvania.'),
    ('UKR', '1986-04-26', 'Chernobyl Unit 4 accident', 'severe', 7, 'Severe reactor accident at the Chernobyl nuclear power plant.'),
    ('JPN', '2011-03-11', 'Fukushima Daiichi accident', 'severe', 7, 'Multiple-unit accident following earthquake and tsunami impacts.')
) as v(country_iso3, event_date, title, severity, ines_level, summary)
left join public.countries c on c.iso3 = v.country_iso3
cross join src
where c.id is not null;
