from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from nuclear_energy.dashboard import (
    _amount_color_kwargs,
    _format_datetime,
    _format_trade_balance,
    _has_positive_amount_counts,
    _selected_country_iso_code,
    _secret_matches,
    _stage_label,
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


def test_transaction_helpers_format_labels_and_country_selection() -> None:
    assert _transaction_type_label("contract_award") == "Contract Award"
    assert _stage_label("public_tender") == "Public Tender"
    assert _selected_country_iso_code("Romania (ROU)") == "ROU"
    assert _selected_country_iso_code("All countries") is None


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
