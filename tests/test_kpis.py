"""Tests for the KPI engine (Milestone 8): unit math + DB integration."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis import kpis
from src.analysis.kpis import KPI


def test_effective_genres_equals_count_when_uniform():
    # A perfectly even spread of k genres has effective breadth exactly k.
    counts = pd.Series([10, 10, 10, 10], index=list("abcd"))
    assert kpis.effective_genres(counts) == pytest.approx(4.0)


def test_effective_genres_drops_when_skewed():
    even = pd.Series([10, 10, 10], index=list("abc"))
    skewed = pd.Series([100, 1, 1], index=list("abc"))
    assert kpis.effective_genres(skewed) < kpis.effective_genres(even)
    assert kpis.effective_genres(skewed) < 3.0


@pytest.mark.parametrize("value,unit,expected", [
    (44.66, "%", "44.7%"),
    (98.0, "min", "98 min"),
    (1.0, "yrs", "1.0 yrs"),
    (2.34, "x", "2.34×"),
    (23.2, "index", "23.2"),
    (8807, "", "8,807"),
])
def test_kpi_formatted(value, unit, expected):
    assert KPI("k", "label", value, unit).formatted() == expected


# --- Integration against the real database ---------------------------------
def test_compute_kpis_totals_are_consistent(db_conn):
    by_key = {k.key: k.value for k in kpis.compute_kpis(db_conn)}
    total = db_conn.execute("SELECT COUNT(*) FROM titles").fetchone()[0]
    assert by_key["total_titles"] == total
    assert by_key["movies"] + by_key["tv_shows"] == total
    assert 0 <= by_key["international_share"] <= 100
