import pytest

from nuclear_energy.db import _capacity_factor_percent, format_vector_literal


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
