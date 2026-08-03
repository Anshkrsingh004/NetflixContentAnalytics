"""Integration tests for automated insight generation (Milestone 12)."""

from __future__ import annotations

from src.analysis import insights


def test_clamp_bounds():
    assert insights._clamp(-5) == 0
    assert insights._clamp(150) == 100
    assert insights._clamp(42.6) == 43


def test_generates_all_insights_ranked(db_conn):
    result = insights.generate_insights(db_conn)
    assert len(result) == len(insights.GENERATORS)
    importances = [i.importance for i in result]
    assert importances == sorted(importances, reverse=True)  # ranked desc


def test_insights_are_well_formed(db_conn):
    for ins in insights.generate_insights(db_conn):
        assert ins.text.strip()
        assert 0 <= ins.importance <= 100
        assert ins.category


def test_key_insights_returns_top_n(db_conn):
    top = insights.key_insights(db_conn, n=5)
    assert len(top) == 5
    full = insights.generate_insights(db_conn)
    assert [i.key for i in top] == [i.key for i in full[:5]]
