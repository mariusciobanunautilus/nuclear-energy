set check_function_bodies = false;

alter type public.document_source_kind add value if not exists 'usaspending';
alter type public.document_source_kind add value if not exists 'eu_ted';
alter type public.document_source_kind add value if not exists 'sec_edgar';
alter type public.document_source_kind add value if not exists 'iaea_pris';
alter type public.document_source_kind add value if not exists 'eia';
alter type public.document_source_kind add value if not exists 'entsoe';

alter table public.nuclear_transactions
  drop constraint if exists nuclear_transactions_stage_check;

alter table public.nuclear_transactions
  add constraint nuclear_transactions_stage_check
  check (
    stage in (
      'detected',
      'confirmed_award',
      'public_tender',
      'regulatory_filing',
      'company_announcement',
      'news_reported'
    )
  );
