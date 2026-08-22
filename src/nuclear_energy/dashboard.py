from __future__ import annotations

import hmac
import os
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

from nuclear_energy.automation import WorkflowDispatchError, trigger_github_workflow
from nuclear_energy.config import get_settings
from nuclear_energy.db import (
    fetch_dashboard_metrics,
    fetch_documents_for_export,
    fetch_energy_country_summaries,
    fetch_energy_system_metrics,
    fetch_energy_years,
    fetch_entity_summaries,
    fetch_event_evidence,
    fetch_event_metrics,
    fetch_events_for_entity,
    fetch_events_for_project,
    fetch_recent_events,
    fetch_recent_documents,
    fetch_review_history,
    fetch_review_metrics,
    fetch_review_queue,
    fetch_watchlist_events,
    fetch_project_summaries,
    fetch_reactor_technology_summaries,
    fetch_source_summaries,
    fetch_source_health,
    fetch_recent_transactions,
    search_documents_keyword,
    fetch_transaction_country_summaries,
    fetch_transaction_metrics,
    fetch_transaction_type_summaries,
    fetch_transaction_year_summaries,
    source_tier_label,
    update_event_review,
)
from nuclear_energy.exports import documents_to_csv, documents_to_markdown


ALL_SOURCES = "All sources"
ALL_COUNTRIES = "All countries"
WORKFLOW_MODES = {
    "Full refresh": "all",
    "Official transactions": "official-transactions",
    "Documents and news": "documents",
    "Energy data": "energy",
}
PAGES = {
    "Daily Tape": {
        "description": "Morning-ready intelligence grouped by official status, materiality, watchlists, themes, and review need.",
        "renderer": "_render_daily_tape",
    },
    "Review Queue": {
        "description": "Triage unreviewed events, promote important facts, correct fields, and preserve review history.",
        "renderer": "_render_review_queue",
    },
    "Events": {
        "description": "Filter the normalized event tape by country, review state, and official-source coverage.",
        "renderer": "_render_events",
    },
    "Signals": {
        "description": "Track public nuclear-sector procurement, award, funding, and transaction evidence.",
        "renderer": "_render_transactions",
    },
    "Energy System": {
        "description": "Compare country electricity systems, nuclear generation, capacity, trade, and recent status events.",
        "renderer": "_render_energy_system",
    },
    "Entities": {
        "description": "Follow companies, agencies, regulators, vendors, and other entities linked to source-backed events.",
        "renderer": "_render_entities",
    },
    "Projects": {
        "description": "Follow plants, reactors, fuel facilities, mines, and programs linked to event evidence.",
        "renderer": "_render_projects",
    },
    "Documents": {
        "description": "Inspect recently ingested public documents by source.",
        "renderer": "_render_documents",
    },
    "Keyword Search": {
        "description": "Search stored public documents when exact terms matter.",
        "renderer": "_render_keyword_search",
    },
    "Source Health": {
        "description": "Check source freshness, extraction coverage, and search readiness.",
        "renderer": "_render_source_health",
    },
    "Exports": {
        "description": "Download source document snapshots for spreadsheet or markdown review.",
        "renderer": "_render_exports",
    },
    "Automation": {
        "description": "Start configured refresh workflows from the dashboard.",
        "renderer": "_render_automation",
    },
}


def main() -> None:
    st.set_page_config(page_title="Nuclear Energy Intelligence", layout="wide")
    _apply_theme()

    metrics = _load_or_stop(fetch_dashboard_metrics)
    source_summaries = _load_or_stop(fetch_source_summaries)
    source_names = [summary.source_name for summary in source_summaries]

    selected_page = _render_sidebar(metrics)
    _render_header(selected_page, PAGES[selected_page]["description"])
    _render_metric_strip(metrics)

    renderer = PAGES[selected_page]["renderer"]
    if renderer == "_render_source_health":
        _render_source_health(source_summaries)
    elif renderer == "_render_documents":
        _render_documents(source_names)
    elif renderer == "_render_keyword_search":
        _render_keyword_search(source_names)
    elif renderer == "_render_exports":
        _render_exports(source_names)
    else:
        globals()[renderer]()


def _apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --surface: #ffffff;
            --surface-muted: #f5f7f9;
            --line: #dbe3ea;
            --ink: #16202a;
            --muted: #647383;
            --accent: #27736b;
            --accent-soft: #e6f3ef;
            --warning-soft: #fff5dc;
        }
        .block-container {
            padding-top: 1.35rem;
            padding-bottom: 3rem;
            max-width: 1500px;
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        div[data-testid="stMetric"] {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 0.75rem 0.85rem;
            min-height: 92px;
        }
        div[data-testid="stMetric"] label {
            color: var(--muted);
        }
        div[data-testid="stMetricValue"] {
            color: var(--ink);
            font-size: 1.5rem;
        }
        section[data-testid="stSidebar"] {
            background: #f7f9fb;
            border-right: 1px solid var(--line);
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label {
            border-radius: 8px;
            padding: 0.18rem 0.35rem;
        }
        .ux-hero {
            border-bottom: 1px solid var(--line);
            padding: 0.2rem 0 1rem 0;
            margin-bottom: 1rem;
        }
        .ux-kicker {
            color: var(--accent);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.2rem;
        }
        .ux-title {
            color: var(--ink);
            font-size: clamp(1.7rem, 2.6vw, 2.5rem);
            font-weight: 760;
            line-height: 1.08;
            margin: 0;
        }
        .ux-description {
            color: var(--muted);
            max-width: 840px;
            margin-top: 0.4rem;
            font-size: 1rem;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--line);
            border-radius: 8px;
            overflow: hidden;
        }
        div[data-testid="stAlert"] {
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar(metrics) -> str:
    with st.sidebar:
        st.markdown("### Nuclear Energy")
        st.caption("Source-backed intelligence workspace")
        selected_page = st.radio("View", list(PAGES), label_visibility="collapsed")
        st.divider()
        embedded_pct = _ratio_percent(metrics.embedded_chunk_count, metrics.chunk_count)
        st.metric("AI-ready", _format_percent_number(embedded_pct))
        st.progress(
            metrics.embedded_chunk_count / metrics.chunk_count if metrics.chunk_count else 0,
            text=f"{metrics.embedded_chunk_count:,} of {metrics.chunk_count:,} chunks",
        )
        st.caption(f"Latest item: {_format_datetime(metrics.latest_published_at) or 'n/a'}")
        return selected_page


def _render_header(title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="ux-hero">
            <div class="ux-kicker">Nuclear Intelligence</div>
            <h1 class="ux-title">{title}</h1>
            <div class="ux-description">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_metric_strip(metrics) -> None:
    columns = st.columns(5)
    columns[0].metric("Documents", f"{metrics.document_count:,}")
    columns[1].metric("With Text", f"{metrics.documents_with_content:,}")
    columns[2].metric("Chunks", f"{metrics.chunk_count:,}")
    columns[3].metric("Embedded", f"{metrics.embedded_chunk_count:,}")
    columns[4].metric("Sources", f"{metrics.source_count:,}")

    if metrics.chunk_count:
        st.progress(
            metrics.embedded_chunk_count / metrics.chunk_count,
            text=f"{metrics.embedded_chunk_count:,} of {metrics.chunk_count:,} chunks embedded",
        )
    if metrics.latest_published_at:
        st.caption(f"Latest published item: {_format_datetime(metrics.latest_published_at)}")


def _render_daily_tape() -> None:
    metrics = _load_or_stop(fetch_event_metrics)
    settings = get_settings()
    window_label = st.selectbox("Window", ["Last 24 hours", "Today", "Last 7 days", "Last 30 days"], index=2)
    since = _daily_window_start(window_label)
    health = _load_or_stop(fetch_source_health)
    source_warnings = _source_freshness_warnings(health)
    sections = {
        "New Official Events": _load_or_stop(fetch_recent_events, limit=50, since=since, official_only=True),
        "Material Changes": _load_or_stop(
            fetch_recent_events,
            limit=50,
            since=since,
            materiality_flags=[
                "large_public_value",
                "fuel_cycle_relevance",
                "project_stage_change",
                "country_policy_shift",
                "supply_risk",
            ],
        ),
        "Watchlist Hits": _load_or_stop(
            fetch_watchlist_events,
            limit=50,
            since=since,
            entities=settings.watchlist_entities,
            projects=settings.watchlist_projects,
            countries=settings.watchlist_countries,
            themes=settings.watchlist_themes,
        ),
        "Marked Important": _load_or_stop(fetch_recent_events, limit=50, since=since, review_status="important"),
        "Fuel Cycle": _load_or_stop(fetch_recent_events, limit=50, since=since, themes=["fuel_cycle"]),
        "Policy & Regulation": _load_or_stop(fetch_recent_events, limit=50, since=since, themes=["policy", "regulation"]),
        "Project Movement": _load_or_stop(
            fetch_recent_events,
            limit=50,
            since=since,
            themes=["project_stage", "construction", "operations", "project_risk"],
        ),
        "Needs Review": _load_or_stop(fetch_recent_events, limit=50, since=since, needs_review=True),
    }
    st.caption(
        "A sectioned morning tape of source-backed nuclear changes. "
        "This is evidence for research, not a trade instruction."
    )
    columns = st.columns(5)
    columns[0].metric("Events", f"{metrics.event_count:,}")
    columns[1].metric("Official", f"{metrics.official_event_count:,}")
    columns[2].metric("Unreviewed", f"{metrics.needs_review_count:,}")
    columns[3].metric("Important", f"{metrics.important_count:,}")
    columns[4].metric("Latest", _format_datetime(metrics.latest_event_date) or "n/a")

    st.caption(_daily_tape_readout(sections, window_label))
    if source_warnings:
        st.warning(" ".join(source_warnings))

    all_section_events = [event for events in sections.values() for event in events]
    if not all_section_events:
        st.info("No normalized events matched this window. Run detect-events, sync-events, and sync-relationships after ingestion.")
        return

    brief = _daily_brief_markdown(
        window_label=window_label,
        sections=sections,
        source_warnings=source_warnings,
    )
    st.download_button(
        "Download Daily Brief",
        data=brief,
        file_name="nuclear-daily-tape.md",
        mime="text/markdown",
        use_container_width=True,
    )

    for title, events in sections.items():
        _render_tape_section(title, events)


def _render_source_health(source_summaries) -> None:
    _render_overview(source_summaries)
    health = _load_or_stop(fetch_source_health)
    frame = _frame(health)
    if frame.empty:
        return

    frame["source_tier"] = frame["source_tier"].map(source_tier_label)
    display_frame = frame.rename(
        columns={
            "source_name": "source",
            "source_kind": "kind",
            "source_tier": "trust_tier",
            "document_count": "documents",
            "latest_published_at": "latest_published",
            "latest_seen_at": "last_seen",
            "latest_run_at": "last_run",
            "latest_run_status": "run_status",
            "latest_run_error": "run_error",
        }
    )
    st.markdown("#### Source Freshness")
    st.caption("Source health shows what the database last saw, how trusted the source class is, and whether recent runs failed.")
    st.dataframe(display_frame, use_container_width=True, hide_index=True)


def _render_tape_section(title: str, events) -> None:
    st.markdown(f"#### {title}")
    if not events:
        st.caption("No matching events in this window.")
        return
    _render_event_table(events, rows=25)


def _render_overview(source_summaries) -> None:
    source_frame = _frame(source_summaries)
    if source_frame.empty:
        st.info("No ingested documents yet.")
        return

    st.info(
        "Overview shows source coverage and processing readiness: what public material was collected, "
        "where text extraction worked, and what is ready for search."
    )
    source_frame["waiting_for_embeddings"] = (
        source_frame["chunk_count"] - source_frame["embedded_chunk_count"]
    ).clip(lower=0)
    source_frame["metadata_only"] = (
        source_frame["document_count"] - source_frame["documents_with_content"]
    ).clip(lower=0)
    source_frame["text_coverage"] = source_frame.apply(
        lambda row: _ratio_percent(row["documents_with_content"], row["document_count"]),
        axis=1,
    )
    source_frame["embedding_coverage"] = source_frame.apply(
        lambda row: _ratio_percent(row["embedded_chunk_count"], row["chunk_count"]),
        axis=1,
    )
    st.caption(_overview_readout(source_frame))

    left, right = st.columns(2)
    with left:
        coverage_frame = source_frame[
            ["source_name", "documents_with_content", "metadata_only"]
        ].melt(
            id_vars="source_name",
            value_vars=["documents_with_content", "metadata_only"],
            var_name="status",
            value_name="documents",
        )
        coverage_frame["status"] = coverage_frame["status"].map(
            {
                "documents_with_content": "Text extracted",
                "metadata_only": "Metadata only",
            }
        )
        fig = px.bar(
            coverage_frame,
            x="source_name",
            y="documents",
            color="status",
            labels={"source_name": "Source", "documents": "Documents", "status": "Status"},
            color_discrete_sequence=["#77c8a0", "#7d8796"],
        )
        fig.update_layout(
            title_text="Source coverage",
            height=360,
            margin=dict(l=10, r=10, t=44, b=10),
            showlegend=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        chunk_frame = source_frame[["source_name", "embedded_chunk_count", "waiting_for_embeddings"]].melt(
            id_vars="source_name",
            value_vars=["embedded_chunk_count", "waiting_for_embeddings"],
            var_name="status",
            value_name="chunks",
        )
        chunk_frame["status"] = chunk_frame["status"].map(
            {
                "embedded_chunk_count": "AI-ready chunks",
                "waiting_for_embeddings": "Waiting for embeddings",
            }
        )
        fig = px.bar(
            chunk_frame,
            x="source_name",
            y="chunks",
            color="status",
            labels={"source_name": "Source", "chunks": "Chunks", "status": "Status"},
            color_discrete_sequence=["#2f7d6d", "#9a6b22"],
        )
        fig.update_layout(
            title_text="Search readiness",
            height=360,
            margin=dict(l=10, r=10, t=44, b=10),
            showlegend=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    display_frame = source_frame[
        [
            "source_name",
            "source_kind",
            "document_count",
            "documents_with_content",
            "text_coverage",
            "chunk_count",
            "embedded_chunk_count",
            "waiting_for_embeddings",
            "embedding_coverage",
            "latest_published_at",
        ]
    ].rename(
        columns={
            "source_name": "source",
            "source_kind": "kind",
            "document_count": "documents",
            "documents_with_content": "with_text",
            "text_coverage": "text_coverage_pct",
            "chunk_count": "chunks",
            "embedded_chunk_count": "embedded",
            "waiting_for_embeddings": "waiting",
            "embedding_coverage": "ai_ready_pct",
            "latest_published_at": "latest",
        }
    )
    display_frame["text_coverage_pct"] = display_frame["text_coverage_pct"].map(_format_percent_number)
    display_frame["ai_ready_pct"] = display_frame["ai_ready_pct"].map(_format_percent_number)
    st.markdown("#### Source Health")
    st.dataframe(display_frame, use_container_width=True, hide_index=True)


def _render_energy_system() -> None:
    metrics = _load_or_stop(fetch_energy_system_metrics)
    summaries = _load_or_stop(fetch_energy_country_summaries, limit=250)
    summary_frame = _frame(summaries)
    if summary_frame.empty:
        st.info("No public energy-system data loaded yet.")
        return

    st.caption(
        "Public annual electricity data from Ember. Imports and exports are shown as net electricity trade."
    )
    columns = st.columns(5)
    columns[0].metric("Countries", f"{metrics.country_count:,}")
    columns[1].metric("Latest Year", _format_year(metrics.latest_year))
    columns[2].metric("Nuclear Generation", _format_twh(metrics.nuclear_generation_twh))
    columns[3].metric("Nuclear Capacity", _format_gw(metrics.nuclear_capacity_gw))
    columns[4].metric("Electricity Demand", _format_twh(metrics.electricity_demand_twh))

    summary_frame["net_trade"] = summary_frame["net_electricity_imports_twh"].map(_format_trade_balance)
    left, right = st.columns([3, 2])
    with left:
        comparison_frame = summary_frame.head(20)
        fig = px.bar(
            comparison_frame,
            x="country_name",
            y="nuclear_generation_twh",
            color="nuclear_share_electricity_percent",
            labels={
                "country_name": "Country",
                "nuclear_generation_twh": "Nuclear generation (TWh)",
                "nuclear_share_electricity_percent": "Nuclear share (%)",
            },
            color_continuous_scale="Tealrose",
        )
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=24, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        capacity_frame = _capacity_chart_frame(summary_frame)
        fig = px.bar(
            capacity_frame,
            x="nuclear_capacity_gw",
            y="country_label",
            color="estimated_capacity_factor_percent",
            orientation="h",
            labels={
                "country_label": "Country",
                "nuclear_capacity_gw": "Nuclear capacity (GW)",
                "estimated_capacity_factor_percent": "Usage (%)",
            },
            color_continuous_scale="Picnic",
        )
        fig.update_layout(height=390, margin=dict(l=10, r=10, t=36, b=10))
        fig.update_yaxes(
            categoryorder="array",
            categoryarray=capacity_frame["country_label"].iloc[::-1].tolist(),
            automargin=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    country_options = _country_options_alphabetical(summaries)
    selected_country = st.selectbox("Country", country_options, key="energy_country")
    selected_iso_code = selected_country.rsplit("(", 1)[-1].rstrip(")")
    years = _load_or_stop(fetch_energy_years, selected_iso_code)
    year_frame = _frame(years)
    if year_frame.empty:
        st.info("No annual energy rows matched.")
        return
    country_transactions = _load_or_stop(fetch_recent_transactions, limit=80, country_iso_code=selected_iso_code)

    latest = _latest_energy_record(years)
    country_columns = st.columns(5)
    country_columns[0].metric("Latest Year", _format_year(latest.year))
    country_columns[1].metric("Nuclear Generation", _format_twh(latest.nuclear_generation_twh))
    country_columns[2].metric("Nuclear Share", _format_percent(latest.nuclear_share_electricity_percent))
    country_columns[3].metric("Nuclear Capacity", _format_gw(latest.nuclear_capacity_gw))
    country_columns[4].metric("Usage", _format_percent(latest.estimated_capacity_factor_percent))

    current_events = _load_or_stop(
        fetch_recent_events,
        limit=8,
        country_iso_code=selected_iso_code,
        since=datetime.now(timezone.utc) - timedelta(days=45),
    )
    st.markdown(f"#### {latest.country_name} Current Nuclear Status")
    st.caption(
        "Recent source-backed events for the selected country. Annual electricity data remains historical; this panel captures current outages, restarts, policy moves, and operational changes."
    )
    _render_energy_current_events(current_events)

    selected_technology_rows = _load_or_stop(fetch_reactor_technology_summaries, selected_iso_code)
    selected_technology_frame = _technology_detail_frame(_frame(selected_technology_rows))
    st.markdown(f"#### {latest.country_name} Reactor Technologies")
    st.caption(
        "Plant and unit-level reactor records for the selected country, including operating status, reactor type, net capacity, and source."
    )
    if selected_technology_frame.empty:
        st.info("No plant-level reactor technology rows are loaded for this country yet.")
    else:
        st.dataframe(selected_technology_frame, use_container_width=True, hide_index=True)

    st.markdown("#### Period Comparison")
    comparison_mode = st.selectbox(
        "Compare",
        ["Latest vs previous year", "Latest vs 5 years ago", "Latest vs 10 years ago", "Custom years"],
        key="energy_period_comparison",
    )
    base_record, compare_record = _select_energy_comparison_records(years, latest, comparison_mode)
    if comparison_mode == "Custom years":
        year_options = [record.year for record in years]
        custom_columns = st.columns(2)
        base_year = custom_columns[0].selectbox(
            "Base year",
            year_options,
            index=year_options.index(base_record.year),
            key="energy_base_year",
        )
        compare_year = custom_columns[1].selectbox(
            "Compare year",
            year_options,
            index=year_options.index(compare_record.year),
            key="energy_compare_year",
        )
        records_by_year = {record.year: record for record in years}
        base_record = records_by_year[base_year]
        compare_record = records_by_year[compare_year]

    comparison = _energy_period_comparison_frame(base_record, compare_record)
    st.caption(_energy_comparison_readout(base_record, compare_record))
    st.dataframe(comparison, use_container_width=True, hide_index=True)

    flow_columns = st.columns([3, 2])
    with flow_columns[0]:
        trend_columns = [
            "nuclear_generation_twh",
            "electricity_generation_twh",
            "electricity_demand_twh",
            "net_electricity_imports_twh",
        ]
        trend_frame = year_frame[["year", *trend_columns]].melt(
            id_vars="year",
            value_vars=trend_columns,
            var_name="metric",
            value_name="value",
        )
        trend_frame = trend_frame.dropna(subset=["value"])
        trend_frame["metric"] = trend_frame["metric"].map(
            {
                "nuclear_generation_twh": "Nuclear generation",
                "electricity_generation_twh": "Total generation",
                "electricity_demand_twh": "Demand / consumption",
                "net_electricity_imports_twh": "Net imports",
            }
        )
        fig = px.line(
            trend_frame,
            x="year",
            y="value",
            color="metric",
            markers=True,
            labels={"year": "Year", "value": "TWh", "metric": "Metric"},
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=24, b=10))
        _add_transaction_markers(fig, country_transactions, trend_frame)
        st.plotly_chart(fig, use_container_width=True)

    with flow_columns[1]:
        capacity_trend = year_frame[["year", "nuclear_capacity_gw"]].dropna(subset=["nuclear_capacity_gw"])
        fig = px.line(
            capacity_trend,
            x="year",
            y="nuclear_capacity_gw",
            markers=True,
            labels={"year": "Year", "nuclear_capacity_gw": "GW"},
        )
        fig.update_traces(line_color="#d24f64")
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=24, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    mix_columns = ["nuclear_generation_twh", "fossil_generation_twh", "renewables_generation_twh"]
    mix_frame = year_frame[["year", *mix_columns]].melt(
        id_vars="year",
        value_vars=mix_columns,
        var_name="source",
        value_name="value",
    )
    mix_frame = mix_frame.dropna(subset=["value"])
    mix_frame["source"] = mix_frame["source"].map(
        {
            "nuclear_generation_twh": "Nuclear",
            "fossil_generation_twh": "Fossil",
            "renewables_generation_twh": "Renewables",
        }
    )
    fig = px.area(
        mix_frame,
        x="year",
        y="value",
        color="source",
        labels={"year": "Year", "value": "TWh", "source": "Source"},
        color_discrete_sequence=["#d24f64", "#7f6a55", "#4e9f7f"],
    )
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=24, b=10))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Underlying Electricity Tables", expanded=False):
        st.markdown("#### Country Electricity Snapshot")
        st.caption(
            "Latest available annual electricity indicators for each country, sorted by nuclear generation and capacity."
        )
        display_summary = summary_frame[
            [
                "country_name",
                "iso_code",
                "latest_year",
                "nuclear_generation_twh",
                "nuclear_capacity_gw",
                "nuclear_share_electricity_percent",
                "electricity_demand_twh",
                "net_trade",
                "estimated_capacity_factor_percent",
            ]
        ].rename(
            columns={
                "country_name": "country",
                "iso_code": "iso",
                "latest_year": "year",
                "nuclear_generation_twh": "nuclear_twh",
                "nuclear_capacity_gw": "capacity_gw",
                "nuclear_share_electricity_percent": "nuclear_share_pct",
                "electricity_demand_twh": "demand_twh",
                "estimated_capacity_factor_percent": "usage_pct",
            }
        )
        st.dataframe(display_summary, use_container_width=True, hide_index=True)

        st.markdown(f"#### {latest.country_name} Annual Electricity History")
        st.caption(
            "Year-by-year generation, capacity, trade, and fuel-mix metrics for the country selected above."
        )
        display_years = year_frame[
            [
                "year",
                "nuclear_generation_twh",
                "nuclear_capacity_gw",
                "nuclear_share_electricity_percent",
                "electricity_generation_twh",
                "electricity_demand_twh",
                "net_electricity_imports_twh",
                "fossil_generation_twh",
                "renewables_generation_twh",
                "clean_generation_twh",
                "estimated_capacity_factor_percent",
            ]
        ].rename(
            columns={
                "nuclear_generation_twh": "nuclear_twh",
                "nuclear_capacity_gw": "capacity_gw",
                "nuclear_share_electricity_percent": "nuclear_share_pct",
                "electricity_generation_twh": "generation_twh",
                "electricity_demand_twh": "demand_twh",
                "net_electricity_imports_twh": "net_imports_twh",
                "fossil_generation_twh": "fossil_twh",
                "renewables_generation_twh": "renewables_twh",
                "clean_generation_twh": "clean_twh",
                "estimated_capacity_factor_percent": "usage_pct",
            }
        )
        st.dataframe(display_years, use_container_width=True, hide_index=True)


def _render_events() -> None:
    country_summaries = _load_or_stop(fetch_transaction_country_summaries, limit=100)
    country_options = [ALL_COUNTRIES] + [
        f"{summary.country_name} ({summary.country_iso_code})"
        for summary in country_summaries
    ]
    controls = st.columns([2, 1, 1])
    selected_country = controls[0].selectbox("Country", country_options, key="events_country")
    review_status = controls[1].selectbox(
        "Review",
        ["All", "unreviewed", "reviewed", "important", "irrelevant", "duplicate", "corrected"],
        key="events_review",
    )
    official_only = controls[2].checkbox("Official only", value=False, key="events_official_only")
    events = _load_or_stop(
        fetch_recent_events,
        limit=100,
        country_iso_code=_selected_country_iso_code(selected_country),
        review_status=None if review_status == "All" else review_status,
        official_only=official_only,
    )
    if not events:
        st.info("No events matched.")
        return

    st.caption(
        "Events normalize public evidence into one auditable tape. Use review status to separate trusted facts, important items, and noise."
    )
    _render_event_table(events, rows=100)


def _render_transactions() -> None:
    country_summaries = _load_or_stop(fetch_transaction_country_summaries, limit=100)
    country_options = [ALL_COUNTRIES] + [
        f"{summary.country_name} ({summary.country_iso_code})"
        for summary in country_summaries
    ]
    selected_country = st.selectbox("Country", country_options, key="transaction_country")
    selected_iso_code = _selected_country_iso_code(selected_country)

    metrics = _load_or_stop(fetch_transaction_metrics, selected_iso_code)
    st.info(
        "This tab counts public nuclear-sector transaction signals: official procurement rows and "
        "detected mentions from public documents or news. Counts show activity, not confirmed investment value."
    )
    columns = st.columns(4)
    columns[0].metric("Public Signals", f"{metrics.transaction_count:,}")
    columns[1].metric("Countries Mentioned", f"{metrics.country_count:,}")
    columns[2].metric("Signals With Amounts", f"{metrics.with_amount_count:,}")
    columns[3].metric("Latest Signal Date", _format_datetime(metrics.latest_transaction_date) or "n/a")

    if metrics.transaction_count == 0:
        st.info("No transaction signals detected yet.")
        return

    st.caption(_transaction_readout(metrics))

    type_summaries = _load_or_stop(fetch_transaction_type_summaries, selected_iso_code)
    year_summaries = _load_or_stop(fetch_transaction_year_summaries, selected_iso_code)
    recent_transactions = _load_or_stop(fetch_recent_transactions, limit=75, country_iso_code=selected_iso_code)

    _render_transaction_evidence_table(recent_transactions)

    st.markdown("#### Activity Patterns")
    left, right = st.columns(2)
    with left:
        year_frame = _frame(year_summaries)
        year_frame["year"] = year_frame["year"].astype(str)
        fig = px.bar(
            year_frame,
            x="year",
            y="transaction_count",
            labels={
                "year": "Year",
                "transaction_count": "Number of signals",
                "with_amount_count": "Signals with public amounts",
            },
            **_amount_color_kwargs(year_frame, "#d8c86b"),
        )
        fig.update_layout(title_text="Signals by year", height=340, margin=dict(l=10, r=10, t=44, b=10))
        fig.update_xaxes(type="category")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        type_frame = _frame(type_summaries)
        type_frame["type_label"] = type_frame["transaction_type"].map(_transaction_type_label)
        fig = px.bar(
            type_frame,
            x="transaction_count",
            y="type_label",
            orientation="h",
            labels={"transaction_count": "Number of signals", "type_label": "Type"},
            **_amount_color_kwargs(type_frame, "#98b9d7"),
        )
        fig.update_layout(
            title_text="Signals by type",
            height=340,
            margin=dict(l=10, r=10, t=44, b=10),
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(fig, use_container_width=True)

    if selected_iso_code is None:
        country_frame = _frame(country_summaries)
        if not country_frame.empty:
            fig = px.bar(
                country_frame.head(20),
                x="country_name",
                y="transaction_count",
                labels={
                    "country_name": "Country",
                    "transaction_count": "Number of signals",
                    "with_amount_count": "Signals with public amounts",
                },
                **_amount_color_kwargs(country_frame, "#d8c86b"),
            )
            fig.update_layout(title_text="Signals by country", height=340, margin=dict(l=10, r=10, t=44, b=10))
            st.plotly_chart(fig, use_container_width=True)


def _render_transaction_evidence_table(recent_transactions) -> None:
    transaction_frame = _frame(recent_transactions)
    if transaction_frame.empty:
        return

    transaction_frame["transaction_type"] = transaction_frame["transaction_type"].map(_transaction_type_label)
    transaction_frame["stage"] = transaction_frame["stage"].map(_stage_label)
    display_frame = transaction_frame[
        [
            "transaction_date",
            "country_name",
            "plant_name",
            "transaction_type",
            "stage",
            "amount_text",
            "confidence",
            "title",
            "summary",
            "source_name",
            "source_url",
        ]
    ].rename(
        columns={
            "transaction_date": "date",
            "country_name": "country",
            "plant_name": "plant",
            "transaction_type": "type",
            "amount_text": "amount",
            "title": "signal",
            "summary": "evidence",
            "source_name": "source",
            "source_url": "url",
        }
    )
    display_frame["country"] = display_frame["country"].fillna("not specified")
    display_frame["plant"] = display_frame["plant"].fillna("not specified")
    display_frame["amount"] = display_frame["amount"].fillna("not public")
    display_frame["confidence"] = display_frame["confidence"].round(2)

    st.markdown("#### Latest Public Signals")
    st.caption("These rows are the source-backed evidence behind the counters and charts.")
    st.dataframe(
        display_frame.head(25),
        use_container_width=True,
        hide_index=True,
        height=360,
        column_config={
            "confidence": st.column_config.ProgressColumn(
                "confidence",
                min_value=0.0,
                max_value=1.0,
                format="%.2f",
            ),
            "url": st.column_config.LinkColumn("source link"),
        },
        )


def _render_energy_current_events(events) -> None:
    display_frame = _energy_current_events_frame(events)
    if display_frame.empty:
        st.info("No recent source-backed nuclear status events are loaded for this country yet.")
        return

    st.dataframe(
        display_frame,
        use_container_width=True,
        hide_index=True,
        height=260,
        column_config={
            "url": st.column_config.LinkColumn("source link"),
        },
    )


def _energy_current_events_frame(events) -> pd.DataFrame:
    event_frame = _frame(events)
    if event_frame.empty:
        return pd.DataFrame()

    event_frame["event_type"] = event_frame["event_type"].map(_event_type_label)
    display_frame = event_frame[
        [
            "event_date",
            "event_type",
            "project_name",
            "title",
            "summary",
            "source_name",
            "source_url",
        ]
    ].rename(
        columns={
            "event_date": "date",
            "event_type": "type",
            "project_name": "plant_or_project",
            "title": "event",
            "summary": "summary",
            "source_name": "source",
            "source_url": "url",
        }
    )
    display_frame["date"] = display_frame["date"].map(_format_date)
    display_frame["plant_or_project"] = display_frame["plant_or_project"].fillna("country-wide")
    return display_frame


def _render_event_table(events, *, rows: int) -> None:
    event_frame = _frame(events)
    if event_frame.empty:
        return
    event_frame["event_type"] = event_frame["event_type"].map(_event_type_label)
    event_frame["event_status"] = event_frame["event_status"].map(_event_status_label)
    event_frame["review_status"] = event_frame["review_status"].map(_review_status_label)
    event_frame["source_tier"] = event_frame["source_tier"].map(source_tier_label)
    event_frame["materiality_flags"] = event_frame["materiality_flags"].map(_join_labels)
    event_frame["themes"] = event_frame["themes"].map(_join_labels)
    display_frame = event_frame[
        [
            "event_date",
            "source_tier",
            "event_type",
            "event_status",
            "review_status",
            "country_name",
            "project_name",
            "amount_text",
            "materiality_flags",
            "themes",
            "source_confidence",
            "evidence_count",
            "title",
            "summary",
            "source_name",
            "source_url",
        ]
    ].rename(
        columns={
            "event_date": "date",
            "source_tier": "trust_tier",
            "event_type": "type",
            "event_status": "status",
            "review_status": "review",
            "country_name": "country",
            "project_name": "project",
            "amount_text": "amount",
            "materiality_flags": "why_it_matters",
            "source_confidence": "confidence",
            "evidence_count": "evidence",
            "title": "event",
            "summary": "source_summary",
            "source_name": "source",
            "source_url": "url",
        }
    )
    display_frame["country"] = display_frame["country"].fillna("not specified")
    display_frame["project"] = display_frame["project"].fillna("not specified")
    display_frame["amount"] = display_frame["amount"].fillna("not public")
    display_frame["confidence"] = display_frame["confidence"].round(2)
    st.dataframe(
        display_frame.head(rows),
        use_container_width=True,
        hide_index=True,
        height=420,
        column_config={
            "date": st.column_config.TextColumn("date", width="small"),
            "trust_tier": st.column_config.TextColumn("trust tier", width="small"),
            "type": st.column_config.TextColumn("type", width="medium"),
            "status": st.column_config.TextColumn("status", width="small"),
            "review": st.column_config.TextColumn("review", width="small"),
            "country": st.column_config.TextColumn("country", width="medium"),
            "project": st.column_config.TextColumn("project", width="medium"),
            "amount": st.column_config.TextColumn("amount", width="small"),
            "why_it_matters": st.column_config.TextColumn("why it matters", width="medium"),
            "themes": st.column_config.TextColumn("themes", width="medium"),
            "confidence": st.column_config.ProgressColumn(
                "confidence",
                min_value=0.0,
                max_value=1.0,
                format="%.2f",
            ),
            "evidence": st.column_config.NumberColumn("evidence", width="small"),
            "event": st.column_config.TextColumn("event", width="large"),
            "source_summary": st.column_config.TextColumn("source summary", width="large"),
            "source": st.column_config.TextColumn("source", width="medium"),
            "url": st.column_config.LinkColumn("source link"),
        },
    )


def _render_review_queue() -> None:
    metrics = _load_or_stop(fetch_review_metrics)
    metric_columns = st.columns(6)
    metric_columns[0].metric("Queue", f"{metrics.queue_count:,}")
    metric_columns[1].metric("Official To Check", f"{metrics.official_unreviewed_count:,}")
    metric_columns[2].metric("Low Confidence", f"{metrics.low_confidence_count:,}")
    metric_columns[3].metric("Important", f"{metrics.important_count:,}")
    metric_columns[4].metric("Corrected", f"{metrics.corrected_count:,}")
    metric_columns[5].metric("Duplicates", f"{metrics.duplicate_count:,}")

    queue = _load_or_stop(fetch_review_queue, limit=50)
    if not queue:
        st.info("No events need review.")
        return

    st.caption("Reviewing events is how the tool becomes a source of truth: keep useful facts, mark noise, and leave context.")
    _render_review_queue_table(queue)
    st.markdown("#### Review Event")
    labels = {f"{item.title[:100]} ({item.id[:8]})": item.id for item in queue}
    items_by_id = {item.id: item for item in queue}
    selected_label = st.selectbox("Event", list(labels), key="review_event_selector")
    selected_event = items_by_id[labels[selected_label]]
    selected_event_key = selected_event.id.replace("-", "_")
    with st.form(f"event_review_form_{selected_event_key}"):
        status = st.selectbox(
            "Decision",
            ["reviewed", "important", "irrelevant", "duplicate", "corrected"],
            format_func=_review_decision_label,
            key=f"review_status_{selected_event_key}",
        )
        duplicate_of = st.text_input(
            "Duplicate of event id",
            placeholder="Only needed when marking as duplicate",
            disabled=status != "duplicate",
            key=f"review_duplicate_of_{selected_event_key}",
        )
        reviewer = st.text_input("Reviewer", placeholder="Optional", key=f"review_reviewer_{selected_event_key}")
        st.markdown("##### Correction Fields")
        correction_columns = st.columns(2)
        corrected_title = correction_columns[0].text_input(
            "Title",
            value=selected_event.title,
            key=f"review_title_{selected_event_key}",
        )
        corrected_country = correction_columns[1].text_input(
            "Country ISO",
            value=selected_event.country_iso_code or "",
            max_chars=3,
            key=f"review_country_{selected_event_key}",
        )
        corrected_project = correction_columns[0].text_input(
            "Project",
            value=selected_event.project_name or "",
            key=f"review_project_{selected_event_key}",
        )
        corrected_amount = correction_columns[1].text_input(
            "Public amount",
            value=selected_event.amount_text or "",
            key=f"review_amount_{selected_event_key}",
        )
        corrected_summary = st.text_area(
            "Summary",
            value=selected_event.summary,
            height=100,
            key=f"review_summary_{selected_event_key}",
        )
        corrected_flags = st.text_input(
            "Why it matters",
            value=", ".join(selected_event.materiality_flags),
            key=f"review_flags_{selected_event_key}",
        )
        corrected_themes = st.text_input(
            "Themes",
            value=", ".join(selected_event.themes),
            key=f"review_themes_{selected_event_key}",
        )
        note = st.text_area("Note", height=90, key=f"review_note_{selected_event_key}")
        submitted = st.form_submit_button("Save review")
    if submitted:
        corrected_fields = _event_correction_payload(
            selected_event,
            title=corrected_title,
            country_iso_code=corrected_country,
            project_name=corrected_project,
            amount_text=corrected_amount,
            summary=corrected_summary,
            materiality_flags=_split_review_values(corrected_flags),
            themes=_split_review_values(corrected_themes),
        )
        _load_or_stop(
            update_event_review,
            selected_event.id,
            review_status=status,
            note=note or None,
            reviewer=reviewer or None,
            duplicate_of_event_id=(duplicate_of.strip() or None) if status == "duplicate" else None,
            corrected_fields=corrected_fields,
        )
        st.success("Review saved.")
        st.rerun()

    selected_event_id = labels[selected_label]
    st.markdown("#### Evidence")
    _render_event_evidence(_load_or_stop(fetch_event_evidence, selected_event_id, limit=10))
    st.markdown("#### Review History")
    _render_review_history(_load_or_stop(fetch_review_history, selected_event_id, limit=10))


def _render_review_queue_table(queue) -> None:
    frame = _frame(queue)
    frame["event_type"] = frame["event_type"].map(_event_type_label)
    frame["event_status"] = frame["event_status"].map(_event_status_label)
    frame["review_status"] = frame["review_status"].map(_review_status_label)
    frame["source_tier"] = frame["source_tier"].map(source_tier_label)
    frame["materiality_flags"] = frame["materiality_flags"].map(_join_labels)
    frame["themes"] = frame["themes"].map(_join_labels)
    frame["review_reasons"] = frame["review_reasons"].map(_join_review_reasons)
    display_frame = frame[
        [
            "review_priority",
            "event_date",
            "source_tier",
            "event_type",
            "event_status",
            "review_status",
            "country_name",
            "project_name",
            "materiality_flags",
            "themes",
            "review_reasons",
            "source_confidence",
            "evidence_count",
            "title",
            "summary",
            "source_name",
            "source_url",
        ]
    ].rename(
        columns={
            "review_priority": "priority",
            "event_date": "date",
            "source_tier": "trust_tier",
            "event_type": "type",
            "event_status": "status",
            "review_status": "review",
            "country_name": "country",
            "project_name": "project",
            "materiality_flags": "why_it_matters",
            "review_reasons": "review_reason",
            "source_confidence": "confidence",
            "evidence_count": "evidence",
            "title": "event",
            "summary": "source_summary",
            "source_name": "source",
            "source_url": "url",
        }
    )
    display_frame["country"] = display_frame["country"].fillna("not specified")
    display_frame["project"] = display_frame["project"].fillna("not specified")
    display_frame["confidence"] = display_frame["confidence"].round(2)
    st.dataframe(
        display_frame,
        use_container_width=True,
        hide_index=True,
        height=360,
        column_config={
            "priority": st.column_config.NumberColumn("priority", width="small"),
            "date": st.column_config.TextColumn("date", width="small"),
            "trust_tier": st.column_config.TextColumn("trust tier", width="small"),
            "type": st.column_config.TextColumn("type", width="medium"),
            "status": st.column_config.TextColumn("status", width="small"),
            "review": st.column_config.TextColumn("review", width="small"),
            "country": st.column_config.TextColumn("country", width="medium"),
            "project": st.column_config.TextColumn("project", width="medium"),
            "why_it_matters": st.column_config.TextColumn("why it matters", width="medium"),
            "themes": st.column_config.TextColumn("themes", width="medium"),
            "review_reason": st.column_config.TextColumn("review reason", width="medium"),
            "confidence": st.column_config.ProgressColumn(
                "confidence",
                min_value=0.0,
                max_value=1.0,
                format="%.2f",
            ),
            "evidence": st.column_config.NumberColumn("evidence", width="small"),
            "event": st.column_config.TextColumn("event", width="large"),
            "source_summary": st.column_config.TextColumn("source summary", width="large"),
            "source": st.column_config.TextColumn("source", width="medium"),
            "url": st.column_config.LinkColumn("source link"),
        },
    )


def _render_event_evidence(evidence) -> None:
    frame = _frame(evidence)
    if frame.empty:
        st.caption("No evidence rows found for this event.")
        return
    frame["source_tier"] = frame["source_tier"].map(source_tier_label)
    display_frame = frame[
        ["published_at", "source_tier", "evidence_kind", "source_name", "snippet", "source_url"]
    ].rename(
        columns={
            "published_at": "published",
            "source_tier": "trust_tier",
            "evidence_kind": "kind",
            "source_name": "source",
            "source_url": "url",
        }
    )
    st.dataframe(
        display_frame,
        use_container_width=True,
        hide_index=True,
        height=260,
        column_config={
            "published": st.column_config.TextColumn("published", width="small"),
            "trust_tier": st.column_config.TextColumn("trust tier", width="small"),
            "kind": st.column_config.TextColumn("kind", width="small"),
            "source": st.column_config.TextColumn("source", width="medium"),
            "snippet": st.column_config.TextColumn("snippet", width="large"),
            "url": st.column_config.LinkColumn("source link"),
        },
    )


def _render_review_history(history) -> None:
    frame = _frame(history)
    if frame.empty:
        st.caption("No review history yet.")
        return
    frame["review_status"] = frame["review_status"].map(_review_status_label)
    frame["previous_status"] = frame["previous_status"].map(lambda value: _review_status_label(value) if value else "")
    frame["review_action"] = frame["review_action"].map(_review_action_label)
    frame["patch_payload"] = frame["patch_payload"].map(_format_patch_payload)
    display_frame = frame[
        [
            "created_at",
            "review_action",
            "previous_status",
            "review_status",
            "duplicate_of_event_id",
            "patch_payload",
            "note",
            "reviewer",
        ]
    ].rename(
        columns={
            "created_at": "when",
            "review_action": "action",
            "previous_status": "from",
            "review_status": "to",
            "duplicate_of_event_id": "duplicate_of",
            "patch_payload": "corrections",
        }
    )
    st.dataframe(display_frame, use_container_width=True, hide_index=True, height=220)


def _render_entities() -> None:
    entities = _load_or_stop(fetch_entity_summaries, limit=150)
    frame = _frame(entities)
    if frame.empty:
        st.info("No entity links yet. Run detect-events and sync-events after applying the event-layer migration.")
        return

    frame["roles"] = frame["roles"].map(_join_labels)
    display_frame = frame.drop(columns=["id"]).rename(
        columns={
            "canonical_name": "entity",
            "entity_type": "type",
            "country_iso_code": "country",
            "event_count": "events",
            "latest_event_date": "latest_event",
        }
    )
    st.caption("Entity profiles group source-backed nuclear events by companies, agencies, regulators, utilities, and vendors.")
    st.dataframe(display_frame, use_container_width=True, hide_index=True, height=320)

    options = {f"{item.canonical_name} ({item.event_count})": item.id for item in entities}
    selected = st.selectbox("Entity Profile", list(options), key="entity_profile")
    events = _load_or_stop(fetch_events_for_entity, options[selected], limit=75)
    st.markdown("#### Entity Event Timeline")
    _render_event_table(events, rows=75)


def _render_projects() -> None:
    projects = _load_or_stop(fetch_project_summaries, limit=150)
    frame = _frame(projects)
    if frame.empty:
        st.info("No project links yet. Run detect-events and sync-events after applying the event-layer migration.")
        return

    frame["event_types"] = frame["event_types"].map(_join_labels)
    display_frame = frame.drop(columns=["id"]).rename(
        columns={
            "canonical_name": "project",
            "project_type": "type",
            "country_iso_code": "iso",
            "country_name": "country",
            "event_count": "events",
            "latest_event_date": "latest_event",
        }
    )
    st.caption("Project profiles group source-backed events by plant, reactor, fuel facility, mine, or program.")
    st.dataframe(display_frame, use_container_width=True, hide_index=True, height=320)

    options = {f"{item.canonical_name} ({item.country_iso_code or 'n/a'}, {item.event_count})": item.id for item in projects}
    selected = st.selectbox("Project Profile", list(options), key="project_profile")
    events = _load_or_stop(fetch_events_for_project, options[selected], limit=75)
    st.markdown("#### Project Event Timeline")
    _render_event_table(events, rows=75)


def _render_documents(source_names: list[str]) -> None:
    controls = st.columns([2, 1])
    source_name = controls[0].selectbox("Source", [ALL_SOURCES] + source_names, key="documents_source")
    limit = controls[1].slider("Rows", min_value=5, max_value=100, value=25, step=5, key="documents_limit")

    documents = _load_or_stop(
        fetch_recent_documents,
        limit=limit,
        source_name=_source_value(source_name),
        preview_chars=420,
    )
    frame = _frame(documents)
    if frame.empty:
        st.info("No documents matched.")
        return

    st.dataframe(
        frame.drop(columns=["id"]),
        use_container_width=True,
        hide_index=True,
        column_config={"url": st.column_config.LinkColumn("url")},
    )


def _render_keyword_search(source_names: list[str]) -> None:
    controls = st.columns([3, 2, 1])
    query = controls[0].text_input("Search", placeholder="reactor licensing, uranium supply, SMR")
    source_name = controls[1].selectbox("Source", [ALL_SOURCES] + source_names, key="search_source")
    limit = controls[2].slider("Results", min_value=5, max_value=50, value=10, step=5)

    if not query.strip():
        recent = _load_or_stop(fetch_recent_documents, limit=10, source_name=_source_value(source_name))
        frame = _frame(recent)
        if not frame.empty:
            st.dataframe(frame.drop(columns=["id"]), use_container_width=True, hide_index=True)
        return

    results = _load_or_stop(
        search_documents_keyword,
        query,
        limit=limit,
        source_name=_source_value(source_name),
    )
    if not results:
        st.info("No keyword matches.")
        return

    for result in results:
        st.markdown(f"#### [{result.title}]({result.url})")
        st.caption(
            f"{result.source_name} | {result.source_kind} | "
            f"{_format_datetime(result.published_at)} | score {result.score:.3f}"
        )
        st.markdown(result.snippet, unsafe_allow_html=True)


def _render_exports(source_names: list[str]) -> None:
    controls = st.columns([2, 1])
    source_name = controls[0].selectbox("Source", [ALL_SOURCES] + source_names, key="exports_source")
    limit = controls[1].slider("Rows", min_value=10, max_value=500, value=100, step=10, key="exports_limit")

    documents = _load_or_stop(
        fetch_documents_for_export,
        limit=limit,
        source_name=_source_value(source_name),
    )
    csv_data = documents_to_csv(documents)
    markdown_data = documents_to_markdown(documents)

    left, right = st.columns(2)
    left.download_button(
        "Download CSV",
        data=csv_data,
        file_name="nuclear-energy-documents.csv",
        mime="text/csv",
        use_container_width=True,
    )
    right.download_button(
        "Download Markdown",
        data=markdown_data,
        file_name="nuclear-energy-documents.md",
        mime="text/markdown",
        use_container_width=True,
    )

    frame = _frame(documents)
    if not frame.empty:
        st.dataframe(frame, use_container_width=True, hide_index=True)


def _render_automation() -> None:
    token = _secret_value("GITHUB_ACTIONS_TOKEN")
    expected_pin = _secret_value("WORKFLOW_TRIGGER_PIN")
    selected_mode = st.radio("Refresh scope", list(WORKFLOW_MODES), horizontal=True)
    pin = st.text_input("PIN", type="password")

    missing_secrets = _missing_workflow_secret_names(token, expected_pin)
    if missing_secrets:
        st.info("Data refresh is not configured yet.")
        st.caption("Missing Streamlit secrets: " + ", ".join(f"`{name}`" for name in missing_secrets))
        return

    if st.button("Refresh data", type="primary", use_container_width=True):
        if not _secret_matches(pin, expected_pin):
            st.error("Incorrect PIN.")
            return

        with st.spinner("Starting data refresh..."):
            try:
                trigger_github_workflow(
                    token=token,
                    owner="mariusciobanunautilus",
                    repo="nuclear-energy",
                    workflow_id="public-ingest.yml",
                    ref="main",
                    inputs={"mode": WORKFLOW_MODES[selected_mode]},
                )
            except WorkflowDispatchError as exc:
                st.error("Data refresh could not be started.")
                with st.expander("Technical detail"):
                    st.code(str(exc))
                return
            except Exception as exc:
                st.error("Data refresh could not be started.")
                with st.expander("Technical detail"):
                    st.code(str(exc))
                return

        st.success("Data refresh started. New documents and events will appear after the background job finishes.")


def _load_or_stop(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        st.error("Database is not connected yet.")
        with st.expander("Connection detail"):
            st.code(str(exc))
        st.stop()


def _frame(items) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(item) for item in items])
    for column in (
        "published_at",
        "latest_published_at",
        "latest_seen_at",
        "latest_run_at",
        "transaction_date",
        "latest_transaction_date",
        "event_date",
        "latest_event_date",
        "created_at",
    ):
        if column in frame.columns:
            frame[column] = frame[column].map(_format_datetime)
    return frame


def _add_transaction_markers(fig, transactions, trend_frame: pd.DataFrame) -> None:
    if not transactions or trend_frame.empty:
        return

    markers = []
    for transaction in transactions:
        if transaction.transaction_date is None:
            continue
        markers.append(
            {
                "year": transaction.transaction_date.year,
                "label": (
                    f"{_transaction_type_label(transaction.transaction_type)}<br>"
                    f"{_format_datetime(transaction.transaction_date)}<br>"
                    f"{transaction.amount_text or 'amount not public'}<br>"
                    f"{transaction.title}"
                ),
            }
        )
    if not markers:
        return

    marker_frame = pd.DataFrame(markers)
    max_value = trend_frame["value"].max()
    marker_y = (float(max_value) if pd.notna(max_value) else 0) * 1.08
    fig.add_scatter(
        x=marker_frame["year"],
        y=[marker_y] * len(marker_frame),
        mode="markers",
        name="Transaction signals",
        marker={"color": "#f2c14e", "size": 11, "symbol": "diamond"},
        text=marker_frame["label"],
        hovertemplate="%{text}<extra></extra>",
    )


def _capacity_chart_frame(summary_frame: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    frame = (
        summary_frame.dropna(subset=["nuclear_capacity_gw"])
        .sort_values(["nuclear_capacity_gw", "country_name"], ascending=[False, True])
        .head(limit)
        .copy()
    )
    if frame.empty:
        return frame
    frame["country_label"] = frame["country_name"] + " (" + frame["iso_code"] + ")"
    return frame


def _technology_detail_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()

    display_frame = frame[
        [
            "plant_name",
            "reactor_name",
            "reactor_status",
            "technology_code",
            "technology_name",
            "net_capacity_mwe",
            "source_title",
            "source_url",
        ]
    ].rename(
        columns={
            "plant_name": "plant",
            "reactor_name": "unit",
            "reactor_status": "status",
            "technology_code": "technology",
            "technology_name": "technology_name",
            "net_capacity_mwe": "net_mwe",
            "source_title": "source",
            "source_url": "source_url",
        }
    )
    display_frame["technology"] = display_frame["technology"].fillna("Unknown")
    return display_frame


def _latest_energy_record(records):
    for record in reversed(records):
        if _has_nuclear_energy_data(record):
            return record
    return records[-1]


def _has_nuclear_energy_data(record) -> bool:
    return any(
        getattr(record, field, None) is not None
        for field in (
            "nuclear_generation_twh",
            "nuclear_capacity_gw",
            "nuclear_share_electricity_percent",
        )
    )


def _select_energy_comparison_records(records, latest, mode: str):
    if len(records) < 2:
        return latest, latest

    years = sorted(record.year for record in records)
    records_by_year = {record.year: record for record in records}
    offsets = {
        "Latest vs previous year": 1,
        "Latest vs 5 years ago": 5,
        "Latest vs 10 years ago": 10,
    }
    offset = offsets.get(mode, 5)
    target_year = latest.year - offset
    candidate_years = [year for year in years if year <= target_year]
    if not candidate_years:
        candidate_years = [year for year in years if year < latest.year]
    base_year = max(candidate_years) if candidate_years else latest.year
    return records_by_year[base_year], latest


def _energy_period_comparison_frame(base_record, compare_record) -> pd.DataFrame:
    rows = []
    metrics = [
        ("Nuclear generation", "nuclear_generation_twh", "TWh", "quantity"),
        ("Nuclear capacity", "nuclear_capacity_gw", "GW", "quantity"),
        ("Nuclear share", "nuclear_share_electricity_percent", "%", "percentage_point"),
        ("Electricity demand", "electricity_demand_twh", "TWh", "quantity"),
        ("Total generation", "electricity_generation_twh", "TWh", "quantity"),
        ("Net electricity imports", "net_electricity_imports_twh", "TWh", "signed_quantity"),
        ("Fossil generation", "fossil_generation_twh", "TWh", "quantity"),
        ("Renewables generation", "renewables_generation_twh", "TWh", "quantity"),
        ("Clean generation", "clean_generation_twh", "TWh", "quantity"),
        ("Usage", "estimated_capacity_factor_percent", "%", "percentage_point"),
    ]
    for label, field, unit, change_kind in metrics:
        base_value = getattr(base_record, field, None)
        compare_value = getattr(compare_record, field, None)
        change = _numeric_change(base_value, compare_value)
        rows.append(
            {
                "metric": label,
                f"{base_record.year}": _format_comparison_value(base_value, unit, field),
                f"{compare_record.year}": _format_comparison_value(compare_value, unit, field),
                "change": _format_comparison_change(change, unit, change_kind),
                "change_pct": _format_comparison_pct_change(base_value, compare_value, change_kind),
            }
        )
    return pd.DataFrame(rows)


def _energy_comparison_readout(base_record, compare_record) -> str:
    country = getattr(compare_record, "country_name", "Selected country")
    parts = []
    for label, field, unit, change_kind in (
        ("nuclear generation", "nuclear_generation_twh", "TWh", "quantity"),
        ("nuclear capacity", "nuclear_capacity_gw", "GW", "quantity"),
        ("nuclear share", "nuclear_share_electricity_percent", "pp", "percentage_point"),
        ("electricity demand", "electricity_demand_twh", "TWh", "quantity"),
        ("net imports", "net_electricity_imports_twh", "TWh", "signed_quantity"),
    ):
        change = _numeric_change(getattr(base_record, field, None), getattr(compare_record, field, None))
        if change is None:
            continue
        if change == 0:
            parts.append(f"{label} was unchanged")
            continue
        direction = "increased" if change > 0 else "decreased"
        magnitude = abs(change)
        if unit == "pp":
            formatted = f"{magnitude:,.1f} percentage points"
        else:
            formatted = _format_quantity(magnitude, unit)
        parts.append(f"{label} {direction} by {formatted}")
    if not parts:
        return f"{country}: no comparable values between {base_record.year} and {compare_record.year}."
    return f"{country}, {base_record.year} to {compare_record.year}: " + "; ".join(parts[:5]) + "."


def _numeric_change(base_value, compare_value) -> float | None:
    if base_value is None or compare_value is None or pd.isna(base_value) or pd.isna(compare_value):
        return None
    return float(compare_value) - float(base_value)


def _format_comparison_value(value, unit: str, field: str) -> str:
    if field == "net_electricity_imports_twh":
        return _format_trade_balance(value)
    return _format_quantity(value, unit)


def _format_comparison_change(change: float | None, unit: str, change_kind: str) -> str:
    if change is None:
        return "n/a"
    if change_kind == "percentage_point":
        return f"{change:+,.1f} pp"
    return f"{change:+,.1f} {unit}"


def _format_comparison_pct_change(base_value, compare_value, change_kind: str) -> str:
    if change_kind in {"percentage_point", "signed_quantity"}:
        return "n/a"
    if base_value is None or compare_value is None or pd.isna(base_value) or pd.isna(compare_value):
        return "n/a"
    base = float(base_value)
    if base == 0:
        return "n/a"
    return f"{(float(compare_value) - base) / abs(base) * 100:+,.1f}%"


def _format_datetime(value: datetime | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return value.strftime("%Y-%m-%d %H:%M")


def _format_date(value) -> str:
    if value is None or pd.isna(value):
        return "date n/a"
    if isinstance(value, str):
        return value[:10]
    return value.strftime("%Y-%m-%d")


def _format_year(value: int | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(int(value))


def _format_twh(value) -> str:
    return _format_quantity(value, "TWh")


def _format_gw(value) -> str:
    return _format_quantity(value, "GW")


def _format_mwe(value) -> str:
    return _format_quantity(value, "MWe")


def _format_percent(value) -> str:
    return _format_quantity(value, "%")


def _format_quantity(value, unit: str) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    number = float(value)
    if abs(number) >= 100:
        return f"{number:,.0f} {unit}"
    return f"{number:,.1f} {unit}"


def _format_trade_balance(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    number = float(value)
    if number > 0:
        return f"{number:,.1f} TWh net imports"
    if number < 0:
        return f"{abs(number):,.1f} TWh net exports"
    return "balanced"


def _transaction_type_label(value: str) -> str:
    return value.replace("_", " ").title()


def _stage_label(value: str) -> str:
    return value.replace("_", " ").title()


def _event_type_label(value: str) -> str:
    return value.replace("_", " ").title()


def _event_status_label(value: str) -> str:
    return value.replace("_", " ").title()


def _review_status_label(value: str) -> str:
    return value.replace("_", " ").title()


def _review_decision_label(value: str) -> str:
    labels = {
        "reviewed": "Confirm",
        "important": "Important",
        "irrelevant": "Noise",
        "duplicate": "Duplicate",
        "corrected": "Corrected",
    }
    return labels.get(value, _review_status_label(value))


def _review_action_label(value: str) -> str:
    labels = {
        "status_update": "Status Update",
        "mark_important": "Marked Important",
        "mark_irrelevant": "Marked Noise",
        "mark_duplicate": "Marked Duplicate",
        "correction": "Correction",
    }
    return labels.get(value, value.replace("_", " ").title())


def _split_review_values(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _join_review_reasons(values) -> str:
    labels = {
        "official_source": "official source",
        "needs_review_status": "needs review",
        "low_confidence": "low confidence",
        "needs_review_flag": "flagged",
        "large_public_value": "large value",
        "fuel_cycle_relevance": "fuel cycle",
        "project_stage_change": "project movement",
        "supply_risk": "supply risk",
    }
    return ", ".join(labels.get(str(value), str(value).replace("_", " ")) for value in values or [])


def _format_patch_payload(value) -> str:
    if not value:
        return ""
    if isinstance(value, dict):
        return "; ".join(f"{key}: {display_value}" for key, display_value in value.items())
    return str(value)


def _event_correction_payload(event, **values) -> dict[str, object]:
    payload: dict[str, object] = {}
    comparisons = {
        "title": getattr(event, "title", None),
        "country_iso_code": getattr(event, "country_iso_code", None) or "",
        "project_name": getattr(event, "project_name", None) or "",
        "amount_text": getattr(event, "amount_text", None) or "",
        "summary": getattr(event, "summary", None),
        "materiality_flags": list(getattr(event, "materiality_flags", []) or []),
        "themes": list(getattr(event, "themes", []) or []),
    }
    for key, new_value in values.items():
        if isinstance(new_value, str):
            new_value = new_value.strip()
        if key in {"materiality_flags", "themes"}:
            new_value = list(new_value or [])
        if new_value != comparisons.get(key):
            payload[key] = new_value
    return payload


def _join_labels(values) -> str:
    if not values:
        return ""
    return ", ".join(str(value).replace("_", " ").title() for value in values)


def _overview_readout(source_frame: pd.DataFrame) -> str:
    documents = int(source_frame["document_count"].sum())
    with_text = int(source_frame["documents_with_content"].sum())
    chunks = int(source_frame["chunk_count"].sum())
    embedded = int(source_frame["embedded_chunk_count"].sum())
    sources = int(len(source_frame))
    text_rate = _ratio_percent(with_text, documents)
    ai_rate = _ratio_percent(embedded, chunks)

    metadata_only_sources = source_frame[source_frame["metadata_only"] > 0]["source_name"].tolist()
    metadata_note = (
        f" Text extraction needs attention for: {', '.join(metadata_only_sources)}."
        if metadata_only_sources
        else " Text extraction is complete for all current sources."
    )
    return (
        f"{documents:,} public documents are tracked across {sources:,} sources. "
        f"{with_text:,} have usable text ({_format_percent_number(text_rate)}), producing {chunks:,} search chunks. "
        f"{embedded:,} chunks are AI-ready ({_format_percent_number(ai_rate)}).{metadata_note}"
    )


def _transaction_readout(metrics) -> str:
    signal_word = _plural(metrics.transaction_count, "signal")
    signal_verb = "is" if metrics.transaction_count == 1 else "are"
    country_word = _plural(metrics.country_count, "country", "countries")
    amount_word = _plural(metrics.with_amount_count, "signal")
    amount_sentence = (
        "No public amount values were found yet, so this view is counting activity rather than deal value."
        if metrics.with_amount_count == 0
        else f"{metrics.with_amount_count:,} {amount_word} include public amount values."
    )
    latest = _format_datetime(metrics.latest_transaction_date) or "n/a"
    return (
        f"{metrics.transaction_count:,} public {signal_word} {signal_verb} in scope across "
        f"{metrics.country_count:,} {country_word}. Latest signal date: {latest}. {amount_sentence}"
    )


def _daily_window_start(window_label: str, *, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if window_label == "Today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if window_label == "Last 24 hours":
        return now - timedelta(hours=24)
    if window_label == "Last 30 days":
        return now - timedelta(days=30)
    return now - timedelta(days=7)


def _daily_tape_readout(sections: dict[str, list], window_label: str) -> str:
    unique_event_ids = {
        getattr(event, "id", f"{section}:{index}")
        for section, events in sections.items()
        for index, event in enumerate(events)
    }
    official_count = len(sections.get("New Official Events", []))
    material_count = len(sections.get("Material Changes", []))
    watchlist_count = len(sections.get("Watchlist Hits", []))
    review_count = len(sections.get("Needs Review", []))
    return (
        f"{len(unique_event_ids):,} unique event(s) matched {window_label.lower()}. "
        f"{official_count:,} official item(s), {material_count:,} material-change item(s), "
        f"{watchlist_count:,} watchlist hit(s), and {review_count:,} item(s) need review."
    )


def _source_freshness_warnings(source_health, *, now: datetime | None = None, stale_hours: int = 36) -> list[str]:
    now = now or datetime.now(timezone.utc)
    warnings = []
    for source in source_health:
        source_name = getattr(source, "source_name", "Unknown source")
        status = getattr(source, "latest_run_status", None)
        if status == "failed":
            warnings.append(f"{source_name} failed on its latest run.")
            continue
        latest_run_at = getattr(source, "latest_run_at", None)
        if latest_run_at is None:
            continue
        if latest_run_at.tzinfo is None:
            latest_run_at = latest_run_at.replace(tzinfo=timezone.utc)
        age_hours = (now - latest_run_at).total_seconds() / 3600
        if age_hours > stale_hours:
            warnings.append(f"{source_name} has not refreshed in {age_hours:.0f} hours.")
    return warnings


def _daily_brief_markdown(
    *,
    window_label: str,
    sections: dict[str, list],
    source_warnings: list[str],
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    lines = [
        f"# Nuclear Daily Tape - {_format_datetime(generated_at)} UTC",
        "",
        _daily_tape_readout(sections, window_label),
        "",
    ]
    if source_warnings:
        lines.extend(["## Source Warnings", ""])
        lines.extend(f"- {warning}" for warning in source_warnings)
        lines.append("")
    for section, events in sections.items():
        lines.extend([f"## {section}", ""])
        if not events:
            lines.extend(["No matching events.", ""])
            continue
        for event in events[:25]:
            date = _format_datetime(getattr(event, "event_date", None)) or "date n/a"
            source = getattr(event, "source_name", None) or "source n/a"
            source_url = getattr(event, "source_url", None)
            title = getattr(event, "title", "Untitled event")
            event_type = _event_type_label(getattr(event, "event_type", "event"))
            country = getattr(event, "country_name", None) or getattr(event, "country_iso_code", None) or "location n/a"
            project = getattr(event, "project_name", None)
            flags = _join_labels(getattr(event, "materiality_flags", []))
            context = f"{country}" + (f" | {project}" if project else "")
            lines.append(f"- **{date} | {event_type} | {context}**: {title}")
            if flags:
                lines.append(f"  - Why it matters: {flags}")
            if source_url:
                lines.append(f"  - Source: [{source}]({source_url})")
            else:
                lines.append(f"  - Source: {source}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else plural or f"{singular}s"


def _ratio_percent(numerator, denominator) -> float:
    if denominator is None or pd.isna(denominator) or float(denominator) == 0:
        return 0.0
    if numerator is None or pd.isna(numerator):
        return 0.0
    return float(numerator) / float(denominator) * 100


def _format_percent_number(value) -> str:
    if value is None or pd.isna(value):
        return "0.0%"
    return f"{float(value):.1f}%"


def _has_positive_amount_counts(frame: pd.DataFrame) -> bool:
    return bool("with_amount_count" in frame.columns and frame["with_amount_count"].fillna(0).max() > 0)


def _amount_color_kwargs(frame: pd.DataFrame, fallback_color: str) -> dict:
    if _has_positive_amount_counts(frame):
        return {
            "color": "with_amount_count",
            "color_continuous_scale": "Tealrose",
        }
    return {"color_discrete_sequence": [fallback_color]}


def _secret_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value.strip()

    try:
        value = st.secrets.get(name)
    except Exception:
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _secret_matches(value: str, expected: str) -> bool:
    return bool(value and expected and hmac.compare_digest(value, expected))


def _missing_workflow_secret_names(token: str | None, expected_pin: str | None) -> list[str]:
    missing = []
    if not token:
        missing.append("GITHUB_ACTIONS_TOKEN")
    if not expected_pin:
        missing.append("WORKFLOW_TRIGGER_PIN")
    return missing


def _selected_country_iso_code(selected_country: str) -> str | None:
    if selected_country == ALL_COUNTRIES:
        return None
    return selected_country.rsplit("(", 1)[-1].rstrip(")")


def _country_options_alphabetical(summaries) -> list[str]:
    return [
        f"{row.country_name} ({row.iso_code})"
        for row in sorted(
            summaries,
            key=lambda row: ((row.country_name or "").casefold(), row.iso_code or ""),
        )
    ]


def _source_value(source_name: str) -> str | None:
    if source_name == ALL_SOURCES:
        return None
    return source_name


if __name__ == "__main__":
    main()
