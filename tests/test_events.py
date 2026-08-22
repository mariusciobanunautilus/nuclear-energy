from datetime import datetime, timezone
from types import SimpleNamespace

from nuclear_energy.extraction.events import detect_nuclear_events


def _document(**kwargs):
    defaults = {
        "id": "22222222-2222-2222-2222-222222222222",
        "title": "Romanian regulator grants license approval for Cernavoda refurbishment",
        "url": "https://example.com/cernavoda-license",
        "source_name": "Federal Register",
        "source_kind": "federal_register",
        "published_at": datetime(2026, 8, 14, tzinfo=timezone.utc),
        "summary": "The nuclear regulator approved the license for work at Cernavoda in Romania.",
        "content": "",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_detect_nuclear_events_extracts_official_license_approval():
    events = detect_nuclear_events(
        [
            _document(
                summary=(
                    "The U.S. Nuclear Regulatory Commission approved the license for "
                    "Westinghouse-supported work at Cernavoda in Romania."
                )
            )
        ]
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "license_approval"
    assert event.event_status == "confirmed"
    assert event.source_tier == "tier_2_official_document"
    assert event.country_iso_code == "ROU"
    assert event.country_name == "Romania"
    assert event.project_name == "Cernavoda"
    assert "official_confirmation" in event.materiality_flags
    assert "project_stage_change" in event.materiality_flags
    assert event.themes == ["regulation", "project_stage"]
    assert event.source_confidence >= 0.7
    assert event.external_id.startswith("doc-event-")
    entity_names = {entity["canonical_name"] for entity in event.raw_payload["matched_entities"]}
    assert "U.S. Nuclear Regulatory Commission" in entity_names
    assert "Westinghouse Electric Company" in entity_names


def test_detect_nuclear_events_marks_discovery_feed_items_for_review():
    events = detect_nuclear_events(
        [
            _document(
                title="French reactor outage reported at Flamanville",
                source_name="GDELT DOC 2.0",
                source_kind="gdelt",
                summary="Flamanville was offline after an unplanned outage in France.",
            )
        ]
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "outage"
    assert event.event_status == "detected"
    assert event.source_tier == "tier_5_discovery_feed"
    assert event.country_iso_code == "FRA"
    assert event.project_name == "Flamanville"
    assert "supply_risk" in event.materiality_flags
    assert "needs_review" in event.materiality_flags


def test_detect_nuclear_events_captures_supply_contract_current_items():
    events = detect_nuclear_events(
        [
            _document(
                title="Doosan Enerbility contracted for Natrium components",
                source_name="World Nuclear News",
                source_kind="rss",
                summary=(
                    "Doosan Enerbility of South Korea has signed a contract for the supply of key equipment "
                    "for TerraPower's first Natrium sodium-cooled fast reactor power plant in Wyoming, USA."
                ),
            )
        ]
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "contract_award"
    assert event.country_iso_code == "USA"
    assert "procurement" in event.themes
    assert "project_stage" in event.themes


def test_detect_nuclear_events_captures_commissioning_milestones():
    events = detect_nuclear_events(
        [
            _document(
                title="First fuel loaded into Tianwan unit 7",
                summary=(
                    "The loading of fuel assemblies has begun at Tianwan unit 7 "
                    "in China's Jiangsu province."
                ),
            )
        ]
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "commissioning_milestone"
    assert event.country_iso_code == "CHN"
    assert "operations" in event.themes


def test_detect_nuclear_events_skips_unlocated_policy_language():
    events = detect_nuclear_events(
        [
            _document(
                title="Government announces energy policy update",
                summary="The new law updates permitting rules for clean energy.",
            )
        ]
    )

    assert events == []
