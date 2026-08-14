set check_function_bodies = false;

alter table public.nuclear_events
  add column if not exists duplicate_of_event_id uuid references public.nuclear_events(id) on delete set null;

alter table public.event_reviews
  add column if not exists previous_status text,
  add column if not exists review_action text not null default 'status_update',
  add column if not exists duplicate_of_event_id uuid references public.nuclear_events(id) on delete set null,
  add column if not exists patch_payload jsonb not null default '{}'::jsonb;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'event_reviews_previous_status_check'
      and conrelid = 'public.event_reviews'::regclass
  ) then
    alter table public.event_reviews
      add constraint event_reviews_previous_status_check
      check (
        previous_status is null
        or previous_status in ('unreviewed', 'reviewed', 'important', 'irrelevant', 'duplicate', 'corrected')
      );
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'event_reviews_review_action_check'
      and conrelid = 'public.event_reviews'::regclass
  ) then
    alter table public.event_reviews
      add constraint event_reviews_review_action_check
      check (
        review_action in ('status_update', 'mark_important', 'mark_irrelevant', 'mark_duplicate', 'correction')
      );
  end if;
end $$;

create index if not exists nuclear_events_duplicate_of_idx
  on public.nuclear_events (duplicate_of_event_id)
  where duplicate_of_event_id is not null;

grant select on public.nuclear_events to anon, authenticated;
grant all on public.nuclear_events, public.event_reviews to service_role;
