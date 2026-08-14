set check_function_bodies = false;

with expected_tiers as (
  select
    id,
    case
      when source_kind::text in ('usaspending', 'eu_ted') then 'tier_1_official_structured'
      when source_kind::text in (
        'eur_lex',
        'federal_register',
        'congress',
        'regulations_gov',
        'iaea_pris',
        'eia',
        'entsoe'
      ) then 'tier_2_official_document'
      when source_kind::text = 'rss' then 'tier_4_reported_media'
      when source_kind::text = 'gdelt' then 'tier_5_discovery_feed'
      else 'unclassified'
    end as source_tier
  from public.ingested_documents
)
update public.ingested_documents as documents
set
  source_tier = expected_tiers.source_tier,
  updated_at = now()
from expected_tiers
where documents.id = expected_tiers.id
  and documents.source_tier is distinct from expected_tiers.source_tier;

update public.nuclear_events as events
set
  source_tier = case
    when documents.source_kind::text in ('usaspending', 'eu_ted') then 'tier_1_official_structured'
    when documents.source_kind::text in (
      'eur_lex',
      'federal_register',
      'congress',
      'regulations_gov',
      'iaea_pris',
      'eia',
      'entsoe'
    ) then 'tier_2_official_document'
    when documents.source_kind::text = 'rss' then 'tier_4_reported_media'
    when documents.source_kind::text = 'gdelt' then 'tier_5_discovery_feed'
    else 'unclassified'
  end,
  updated_at = now()
from public.ingested_documents as documents
where events.source_document_id = documents.id
  and events.source_tier is distinct from case
    when documents.source_kind::text in ('usaspending', 'eu_ted') then 'tier_1_official_structured'
    when documents.source_kind::text in (
      'eur_lex',
      'federal_register',
      'congress',
      'regulations_gov',
      'iaea_pris',
      'eia',
      'entsoe'
    ) then 'tier_2_official_document'
    when documents.source_kind::text = 'rss' then 'tier_4_reported_media'
    when documents.source_kind::text = 'gdelt' then 'tier_5_discovery_feed'
    else 'unclassified'
  end;

update public.event_evidence as evidence
set source_tier = case
  when documents.source_kind::text in ('usaspending', 'eu_ted') then 'tier_1_official_structured'
  when documents.source_kind::text in (
    'eur_lex',
    'federal_register',
    'congress',
    'regulations_gov',
    'iaea_pris',
    'eia',
    'entsoe'
  ) then 'tier_2_official_document'
  when documents.source_kind::text = 'rss' then 'tier_4_reported_media'
  when documents.source_kind::text = 'gdelt' then 'tier_5_discovery_feed'
  else 'unclassified'
end
from public.ingested_documents as documents
where evidence.document_id = documents.id
  and evidence.source_tier is distinct from case
    when documents.source_kind::text in ('usaspending', 'eu_ted') then 'tier_1_official_structured'
    when documents.source_kind::text in (
      'eur_lex',
      'federal_register',
      'congress',
      'regulations_gov',
      'iaea_pris',
      'eia',
      'entsoe'
    ) then 'tier_2_official_document'
    when documents.source_kind::text = 'rss' then 'tier_4_reported_media'
    when documents.source_kind::text = 'gdelt' then 'tier_5_discovery_feed'
    else 'unclassified'
  end;
