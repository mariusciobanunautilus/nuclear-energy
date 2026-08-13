from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from nuclear_energy.db import (
    fetch_dashboard_metrics,
    fetch_documents_for_export,
    fetch_energy_country_summaries,
    fetch_energy_system_metrics,
    fetch_energy_years,
    fetch_recent_documents,
    fetch_source_summaries,
    search_documents_keyword,
)
from nuclear_energy.exports import documents_to_csv, documents_to_markdown


ALL_SOURCES = "All sources"


def main() -> None:
    st.set_page_config(page_title="Nuclear Energy Intelligence", layout="wide")
    st.title("Nuclear Energy Intelligence")

    metrics = _load_or_stop(fetch_dashboard_metrics)
    source_summaries = _load_or_stop(fetch_source_summaries)
    source_names = [summary.source_name for summary in source_summaries]

    _render_metric_strip(metrics)

    tabs = st.tabs(["Overview", "Energy System", "Documents", "Keyword Search", "Exports"])
    with tabs[0]:
        _render_overview(source_summaries)
    with tabs[1]:
        _render_energy_system()
    with tabs[2]:
        _render_documents(source_names)
    with tabs[3]:
        _render_keyword_search(source_names)
    with tabs[4]:
        _render_exports(source_names)


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

    source_frame["waiting_for_embeddings"] = (
        source_frame["chunk_count"] - source_frame["embedded_chunk_count"]
    ).clip(lower=0)

    left, right = st.columns(2)
    with left:
        fig = px.bar(
            source_frame,
            x="source_name",
            y="document_count",
            color="source_kind",
            labels={"source_name": "Source", "document_count": "Documents", "source_kind": "Kind"},
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=24, b=10), showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        chunk_frame = source_frame[["source_name", "embedded_chunk_count", "waiting_for_embeddings"]]
        fig = px.bar(
            chunk_frame,
            x="source_name",
            y=["embedded_chunk_count", "waiting_for_embeddings"],
            labels={"source_name": "Source", "value": "Chunks", "variable": "Status"},
            color_discrete_sequence=["#2f7d6d", "#9a6b22"],
        )
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=24, b=10), showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

    display_frame = source_frame[
        [
            "source_name",
            "source_kind",
            "document_count",
            "documents_with_content",
            "chunk_count",
            "embedded_chunk_count",
            "latest_published_at",
        ]
    ].rename(
        columns={
            "source_name": "source",
            "source_kind": "kind",
            "document_count": "documents",
            "documents_with_content": "with_text",
            "chunk_count": "chunks",
            "embedded_chunk_count": "embedded",
            "latest_published_at": "latest",
        }
    )
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
    for column in ("published_at", "latest_published_at"):
        if column in frame.columns:
            frame[column] = frame[column].map(_format_datetime)
    return frame


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


def _source_value(source_name: str) -> str | None:
    if source_name == ALL_SOURCES:
        return None
    return source_name


if __name__ == "__main__":
    main()
