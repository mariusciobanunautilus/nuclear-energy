from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

from nuclear_energy.dashboard import (
    _amount_color_kwargs,
    _daily_brief_markdown,
    _daily_tape_readout,
    _daily_window_start,
    _event_status_label,
    _event_type_label,
    _event_correction_payload,
    _format_patch_payload,
    _format_datetime,
    _format_trade_balance,
    _has_positive_amount_counts,
    _join_labels,
    _join_review_reasons,
    _energy_comparison_readout,
    _energy_period_comparison_frame,
    _latest_energy_record,
    _missing_workflow_secret_names,
    _overview_readout,
    _review_action_label,
    _review_decision_label,
    _review_status_label,
    _selected_country_iso_code,
    _secret_matches,
    _split_review_values,
    _source_freshness_warnings,
    _stage_label,
    _transaction_readout,
    _transaction_type_label,
)


def test_format_datetime_handles_missing_pandas_values() -> None:
    assert _format_datetime(None) == ""
    assert _format_datetime(pd.NaT) == ""


def test_format_datetime_formats_datetime_values() -> None:
    value = datetime(2026, 8, 13, 21, 30, tzinfo=timezone.utc)

    assert _format_datetime(value) == "2026-08-13 21:30"


def test_format_trade_balance_labels_net_imports_and_exports() -> None:
    assert _format_trade_balance(2.5) == "2.5 TWh net imports"
    assert _format_trade_balance(-3.25) == "3.2 TWh net exports"
    assert _format_trade_balance(0) == "balanced"


def test_latest_energy_record_prefers_latest_nuclear_populated_year() -> None:
    records = [
        SimpleNamespace(year=2022, nuclear_generation_twh=10, nuclear_capacity_gw=1.4, nuclear_share_electricity_percent=20),
        SimpleNamespace(year=2023, nuclear_generation_twh=None, nuclear_capacity_gw=None, nuclear_share_electricity_percent=None),
    ]

    assert _latest_energy_record(records).year == 2022


def test_energy_period_comparison_formats_quantities_and_percentage_points() -> None:
    base = SimpleNamespace(
        year=2020,
        country_name="Romania",
        nuclear_generation_twh=10,
        nuclear_capacity_gw=1.4,
        nuclear_share_electricity_percent=18,
        electricity_demand_twh=50,
        electricity_generation_twh=55,
        net_electricity_imports_twh=2,
        fossil_generation_twh=20,
        renewables_generation_twh=15,
        clean_generation_twh=30,
        estimated_capacity_factor_percent=81,
    )
    compare = SimpleNamespace(
        year=2025,
        country_name="Romania",
        nuclear_generation_twh=12,
        nuclear_capacity_gw=1.4,
        nuclear_share_electricity_percent=21,
        electricity_demand_twh=60,
        electricity_generation_twh=63,
        net_electricity_imports_twh=-1,
        fossil_generation_twh=18,
        renewables_generation_twh=20,
        clean_generation_twh=35,
        estimated_capacity_factor_percent=98,
    )

    frame = _energy_period_comparison_frame(base, compare)
    share_row = frame[frame["metric"] == "Nuclear share"].iloc[0]
    demand_row = frame[frame["metric"] == "Electricity demand"].iloc[0]
    imports_row = frame[frame["metric"] == "Net electricity imports"].iloc[0]

    assert share_row["change"] == "+3.0 pp"
    assert share_row["change_pct"] == "n/a"
    assert demand_row["change_pct"] == "+20.0%"
    assert imports_row["2025"] == "1.0 TWh net exports"

    readout = _energy_comparison_readout(base, compare)
    assert "Romania, 2020 to 2025" in readout
    assert "nuclear generation increased by 2.0 TWh" in readout
    assert "nuclear share increased by 3.0 percentage points" in readout


def test_overview_readout_explains_source_coverage_and_readiness() -> None:
    frame = pd.DataFrame(
        [
            {
                "source_name": "EUR-Lex",
                "document_count": 5,
                "documents_with_content": 5,
                "chunk_count": 5,
                "embedded_chunk_count": 0,
                "metadata_only": 0,
            },
            {
                "source_name": "IAEA Top News",
                "document_count": 5,
                "documents_with_content": 0,
                "chunk_count": 0,
                "embedded_chunk_count": 0,
                "metadata_only": 5,
            },
        ]
    )

    readout = _overview_readout(frame)

    assert "10 public documents" in readout
    assert "5 have usable text (50.0%)" in readout
    assert "0 chunks are AI-ready (0.0%)" in readout
    assert "IAEA Top News" in readout


def test_transaction_helpers_format_labels_and_country_selection() -> None:
    assert _transaction_type_label("contract_award") == "Contract Award"
    assert _stage_label("public_tender") == "Public Tender"
    assert _selected_country_iso_code("Romania (ROU)") == "ROU"
    assert _selected_country_iso_code("All countries") is None


def test_event_helpers_format_source_of_truth_labels() -> None:
    assert _event_type_label("fuel_supply") == "Fuel Supply"
    assert _event_status_label("needs_review") == "Needs Review"
    assert _review_status_label("important") == "Important"
    assert _review_decision_label("irrelevant") == "Noise"
    assert _review_action_label("mark_duplicate") == "Marked Duplicate"
    assert _join_labels(["official_confirmation", "fuel_cycle_relevance"]) == (
        "Official Confirmation, Fuel Cycle Relevance"
    )
    assert _join_review_reasons(["official_source", "low_confidence"]) == "official source, low confidence"
    assert _join_labels([]) == ""


def test_review_correction_helpers_capture_only_changed_fields() -> None:
    event = SimpleNamespace(
        title="Original title",
        country_iso_code="USA",
        project_name="Project A",
        amount_text="USD 10m",
        summary="Original summary",
        materiality_flags=["official_confirmation"],
        themes=["policy"],
    )

    payload = _event_correction_payload(
        event,
        title="Original title",
        country_iso_code="USA",
        project_name="Project B",
        amount_text="USD 10m",
        summary="Sharper summary",
        materiality_flags=["official_confirmation", "fuel_cycle_relevance"],
        themes=["policy"],
    )

    assert payload == {
        "project_name": "Project B",
        "summary": "Sharper summary",
        "materiality_flags": ["official_confirmation", "fuel_cycle_relevance"],
    }
    assert _split_review_values("policy, fuel_cycle, ") == ["policy", "fuel_cycle"]
    assert _format_patch_payload(payload) == (
        "project_name: Project B; summary: Sharper summary; "
        "materiality_flags: ['official_confirmation', 'fuel_cycle_relevance']"
    )


def test_transaction_readout_explains_public_signals_without_amounts() -> None:
    metrics = SimpleNamespace(
        transaction_count=8,
        country_count=7,
        with_amount_count=0,
        latest_transaction_date=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )

    readout = _transaction_readout(metrics)

    assert "8 public signals" in readout
    assert "7 countries" in readout
    assert "No public amount values" in readout


def test_amount_color_helpers_skip_colorbar_without_public_amounts() -> None:
    frame = pd.DataFrame([{"with_amount_count": 0}, {"with_amount_count": 0}])

    assert _has_positive_amount_counts(frame) is False
    assert _amount_color_kwargs(frame, "#abc") == {"color_discrete_sequence": ["#abc"]}


def test_amount_color_helpers_use_amounts_when_available() -> None:
    frame = pd.DataFrame([{"with_amount_count": 0}, {"with_amount_count": 2}])

    assert _has_positive_amount_counts(frame) is True
    assert _amount_color_kwargs(frame, "#abc")["color"] == "with_amount_count"


def test_secret_matches_requires_exact_pin() -> None:
    assert _secret_matches("1234", "1234") is True
    assert _secret_matches("1234", "9999") is False
    assert _secret_matches("", "1234") is False


def test_missing_workflow_secret_names_reports_specific_missing_values() -> None:
    assert _missing_workflow_secret_names(None, None) == [
        "GITHUB_ACTIONS_TOKEN",
        "WORKFLOW_TRIGGER_PIN",
    ]
    assert _missing_workflow_secret_names("token", None) == ["WORKFLOW_TRIGGER_PIN"]
    assert _missing_workflow_secret_names(None, "1234") == ["GITHUB_ACTIONS_TOKEN"]
    assert _missing_workflow_secret_names("token", "1234") == []


def test_daily_window_start_returns_expected_utc_ranges() -> None:
    now = datetime(2026, 8, 14, 12, 30, tzinfo=timezone.utc)

    assert _daily_window_start("Today", now=now) == datetime(2026, 8, 14, tzinfo=timezone.utc)
    assert _daily_window_start("Last 24 hours", now=now) == datetime(2026, 8, 13, 12, 30, tzinfo=timezone.utc)
    assert _daily_window_start("Last 7 days", now=now) == datetime(2026, 8, 7, 12, 30, tzinfo=timezone.utc)
    assert _daily_window_start("Last 30 days", now=now) == datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)


def test_daily_tape_readout_counts_unique_events() -> None:
    event = SimpleNamespace(id="event-1")
    sections = {
        "New Official Events": [event],
        "Material Changes": [event],
        "Watchlist Hits": [],
        "Needs Review": [SimpleNamespace(id="event-2")],
    }

    readout = _daily_tape_readout(sections, "Last 7 days")

    assert "2 unique event(s)" in readout
    assert "1 official item(s)" in readout
    assert "1 item(s) need review" in readout


def test_source_freshness_warnings_report_failed_and_stale_sources() -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=timezone.utc)
    health = [
        SimpleNamespace(source_name="EU TED", latest_run_status="failed", latest_run_at=now),
        SimpleNamespace(
            source_name="USAspending.gov",
            latest_run_status="succeeded",
            latest_run_at=datetime(2026, 8, 12, 0, tzinfo=timezone.utc),
        ),
    ]

    warnings = _source_freshness_warnings(health, now=now, stale_hours=24)

    assert "EU TED failed on its latest run." in warnings
    assert "USAspending.gov has not refreshed in 60 hours." in warnings


def test_daily_brief_markdown_groups_sections_with_sources() -> None:
    event = SimpleNamespace(
        id="event-1",
        event_date=datetime(2026, 8, 14, 9, tzinfo=timezone.utc),
        event_type="fuel_supply",
        country_name="United States",
        country_iso_code="USA",
        project_name=None,
        title="DOE announces HALEU fuel award",
        materiality_flags=["official_confirmation", "fuel_cycle_relevance"],
        source_name="USAspending.gov",
        source_url="https://example.com/award",
    )

    brief = _daily_brief_markdown(
        window_label="Last 7 days",
        sections={"Fuel Cycle": [event], "Needs Review": []},
        source_warnings=["GDELT failed on its latest run."],
        generated_at=datetime(2026, 8, 14, 12, tzinfo=timezone.utc),
    )

    assert "# Nuclear Daily Tape - 2026-08-14 12:00 UTC" in brief
    assert "## Source Warnings" in brief
    assert "## Fuel Cycle" in brief
    assert "DOE announces HALEU fuel award" in brief
    assert "[USAspending.gov](https://example.com/award)" in brief
