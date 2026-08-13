from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from nuclear_energy.dashboard import _format_datetime


def test_format_datetime_handles_missing_pandas_values() -> None:
    assert _format_datetime(None) == ""
    assert _format_datetime(pd.NaT) == ""


def test_format_datetime_formats_datetime_values() -> None:
    value = datetime(2026, 8, 13, 21, 30, tzinfo=timezone.utc)

    assert _format_datetime(value) == "2026-08-13 21:30"
