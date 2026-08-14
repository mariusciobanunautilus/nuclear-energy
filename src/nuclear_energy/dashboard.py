from __future__ import annotations

import hmac
import os
from dataclasses import asdict
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from nuclear_energy.automation import GITHUB_ACTIONS_URL, WorkflowDispatchError, trigger_github_workflow
from nuclear_energy.db import (
    fetch_dashboard_metrics,
    fetch_documents_for_export,
    fetch_energy_country_summaries,
    fetch_energy_system_metrics,
    fetch_energy_years,
    fetch_recent_documents,
    fetch_source_summaries,
    fetch_recent_transactions,
    search_documents_keyword,
    fetch_transaction_country_summaries,
    fetch_transaction_metrics,
    fetch_transaction_type_summaries,
    fetch_transaction_year_summaries,
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


def main() -> None:
    st.set_page_config(page_title="Nuclear Energy Intelligence", layout="wide")
    st.title("Nuclear Energy Intelligence")

    metrics = _load_or_stop(fetch_dashboard_metrics)
    source_summaries = _load_or_stop(fetch_source_summaries)
    source_names = [summary.source_name for summary in source_summaries]

    _render_metric_strip(metrics)

    tabs = st.tabs([
        "Overview",
        "Energy System",
        "Transactions",
        "Documents",
        "Keyword Search",
        "Exports",
        "Automation",
    ])
    with tabs[0]:
        _render_overview(source_summaries)
    with tabs[1]:
        _render_energy_system()
    with tabs[2]:
        _render_transactions()
    with tabs[3]:
        _render_documents(source_names)
    with tabs[4]:
        _render_keyword_search(source_names)
    with tabs[5]:
        _render_exports(source_names)
    with tabs[6]:
        _render_automation()


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
        capacity_frame = summary_frame.dropna(subset=["nuclear_capacity_gw"]).head(20)
        fig = px.bar(
            capacity_frame,
            x="nuclear_capacity_gw",
            y="country_name",
            color="estimated_capacity_factor_percent",
            orientation="h",
            labels={
                "country_name": "Country",
                "nuclear_capacity_gw": "Nuclear capacity (GW)",
                "estimated_capacity_factor_percent": "Usage (%)",
            },
            color_continuous_scale="Picnic",
        )
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=24, b=10), yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    country_options = [f"{row.country_name} ({row.iso_code})" for row in summaries]
    selected_country = st.selectbox("Country", country_options, key="energy_country")
    selected_iso_code = selected_country.rsplit("(", 1)[-1].rstrip(")")
    years = _load_or_stop(fetch_energy_years, selected_iso_code)
    year_frame = _frame(years)
    if year_frame.empty:
        st.info("No annual energy rows matched.")
        return
    country_transactions = _load_or_stop(fetch_recent_transactions, limit=80, country_iso_code=selected_iso_code)

    latest = years[-1]
    country_columns = st.columns(5)
    country_columns[0].metric("Latest Year", _format_year(latest.year))
    country_columns[1].metric("Nuclear Generation", _format_twh(latest.nuclear_generation_twh))
    country_columns[2].metric("Nuclear Share", _format_percent(latest.nuclear_share_electricity_percent))
    country_columns[3].metric("Nuclear Capacity", _format_gw(latest.nuclear_capacity_gw))
    country_columns[4].metric("Usage", _format_percent(latest.estimated_capacity_factor_percent))

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
    selected_mode = st.radio("Workflow", list(WORKFLOW_MODES), horizontal=True)
    pin = st.text_input("PIN", type="password")

    missing_secrets = _missing_workflow_secret_names(token, expected_pin)
    if missing_secrets:
        st.info("Workflow trigger is not configured yet.")
        st.caption("Missing Streamlit secrets: " + ", ".join(f"`{name}`" for name in missing_secrets))
        return

    if st.button("Run workflow", type="primary", use_container_width=True):
        if not _secret_matches(pin, expected_pin):
            st.error("Incorrect PIN.")
            return

        with st.spinner("Starting workflow..."):
            try:
                result = trigger_github_workflow(
                    token=token,
                    owner="mariusciobanunautilus",
                    repo="nuclear-energy",
                    workflow_id="public-ingest.yml",
                    ref="main",
                    inputs={"mode": WORKFLOW_MODES[selected_mode]},
                )
            except WorkflowDispatchError as exc:
                st.error(str(exc))
                return
            except Exception as exc:
                st.error(f"GitHub request failed: {exc}")
                return

        st.success("Workflow started.")
        st.markdown(f"[Open GitHub Actions]({result.html_url or GITHUB_ACTIONS_URL})")


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
    for column in ("published_at", "latest_published_at", "transaction_date", "latest_transaction_date"):
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


def _format_datetime(value: datetime | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return value.strftime("%Y-%m-%d %H:%M")


def _format_year(value: int | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(int(value))


def _format_twh(value) -> str:
    return _format_quantity(value, "TWh")


def _format_gw(value) -> str:
    return _format_quantity(value, "GW")


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


def _source_value(source_name: str) -> str | None:
    if source_name == ALL_SOURCES:
        return None
    return source_name


if __name__ == "__main__":
    main()
