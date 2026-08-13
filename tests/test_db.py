import pytest

from nuclear_energy.db import format_vector_literal


def test_format_vector_literal_uses_pgvector_syntax():
    assert format_vector_literal([0, 1.25, -3.5]) == "[0,1.25,-3.5]"


def test_format_vector_literal_rejects_empty_vector():
    with pytest.raises(ValueError):
        format_vector_literal([])


def test_format_vector_literal_rejects_non_finite_values():
    with pytest.raises(ValueError):
        format_vector_literal([float("nan")])
