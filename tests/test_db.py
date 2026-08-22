import pytest
from sqlalchemy.dialects.postgresql import insert

from nuclear_energy.db import (
    _capacity_factor_percent,
    _document_upsert_update_columns,
    format_vector_literal,
    ingested_documents,
    review_action_for_status,
    source_tier_for_kind,
    source_tier_label,
)
from nuclear_energy.models import SourceKind


def test_format_vector_literal_uses_pgvector_syntax():
    assert format_vector_literal([0, 1.25, -3.5]) == "[0,1.25,-3.5]"


def test_format_vector_literal_rejects_empty_vector():
    with pytest.raises(ValueError):
        format_vector_literal([])


def test_format_vector_literal_rejects_non_finite_values():
    with pytest.raises(ValueError):
        format_vector_literal([float("nan")])


def test_capacity_factor_percent_estimates_annual_nuclear_usage():
    assert round(_capacity_factor_percent(10.512, 1.4), 1) == 85.7
    assert _capacity_factor_percent(None, 1.4) is None
    assert _capacity_factor_percent(10.512, 0) is None


def test_document_upsert_preserves_identity_and_created_at():
    statement = insert(ingested_documents)

    assert set(_document_upsert_update_columns(statement)) == {
        "source_name",
        "title",
        "url",
        "published_at",
        "summary",
        "content",
        "authors",
        "tags",
        "raw_payload",
        "source_tier",
        "last_seen_at",
        "updated_at",
    }


def test_source_tier_for_kind_ranks_source_trust():
    assert source_tier_for_kind(SourceKind.usaspending) == "tier_1_official_structured"
    assert source_tier_for_kind("eu_ted") == "tier_1_official_structured"
    assert source_tier_for_kind(SourceKind.federal_register) == "tier_2_official_document"
    assert source_tier_for_kind(SourceKind.rss) == "tier_4_reported_media"
    assert source_tier_for_kind(SourceKind.rss, "IAEA Top News") == "tier_2_official_document"
    assert source_tier_for_kind(SourceKind.rss, "NRC News Releases") == "tier_2_official_document"
    assert source_tier_for_kind(SourceKind.gdelt) == "tier_5_discovery_feed"
    assert source_tier_label("tier_1_official_structured") == "Tier 1 - Official Structured"
    assert source_tier_label("unknown") == "Unclassified"


def test_review_action_for_status_names_review_workflow_actions():
    assert review_action_for_status("reviewed") == "status_update"
    assert review_action_for_status("important") == "mark_important"
    assert review_action_for_status("irrelevant") == "mark_irrelevant"
    assert review_action_for_status("duplicate") == "mark_duplicate"
    assert review_action_for_status("corrected") == "correction"
    assert review_action_for_status("reviewed", has_corrections=True) == "correction"
