from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from nuclear_energy.db import (
    fetch_dashboard_metrics,
    fetch_documents_for_export,
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

    tabs = st.tabs(["Overview", "Documents", "Keyword Search", "Exports"])
    with tabs[0]:
        _render_overview(source_summaries)
    with tabs[1]:
        _render_documents(source_names)
    with tabs[2]:
        _render_keyword_search(source_names)
    with tabs[3]:
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
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M")


def _source_value(source_name: str) -> str | None:
    if source_name == ALL_SOURCES:
        return None
    return source_name


if __name__ == "__main__":
    main()
