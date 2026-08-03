"""Integration tests for the SQL analytics layer (Milestone 6)."""

from __future__ import annotations

import pytest

from src.analysis import sql_analytics

QUERY_KEYS = [q.key for q in sql_analytics.QUERIES]


@pytest.mark.parametrize("key", QUERY_KEYS)
def test_every_query_runs_and_returns_rows(key, db_conn):
    df = sql_analytics.run_query(key, db_conn)
    assert not df.empty, f"query {key} returned no rows"


def test_content_type_split_covers_whole_catalog(db_conn):
    df = sql_analytics.run_query("content_type_split", db_conn)
    total = db_conn.execute("SELECT COUNT(*) FROM titles").fetchone()[0]
    assert df["n_titles"].sum() == total
    assert df["pct_of_catalog"].sum() == pytest.approx(100.0, abs=0.1)


def test_top_countries_excludes_unknown_and_is_sorted(db_conn):
    df = sql_analytics.run_query("top_countries", db_conn)
    assert "Unknown" not in set(df["country_name"])
    assert len(df) <= 15
    assert df["n_titles"].is_monotonic_decreasing


def test_catalog_growth_cumulative_is_monotonic(db_conn):
    df = sql_analytics.run_query("catalog_growth_by_year", db_conn)
    assert df["cumulative_titles"].is_monotonic_increasing
    # cumulative ends at the total number of dated titles
    dated = db_conn.execute(
        "SELECT COUNT(*) FROM titles WHERE year_added IS NOT NULL").fetchone()[0]
    assert int(df["cumulative_titles"].iloc[-1]) == dated


def test_content_by_decade_columns_sum_to_total(db_conn):
    df = sql_analytics.run_query("content_by_decade", db_conn)
    assert (df["movies"] + df["tv_shows"] == df["total"]).all()


def test_genre_leaders_are_rank_one_only(db_conn):
    df = sql_analytics.run_query("genre_leaders_by_country", db_conn)
    # one row per country (the single top genre)
    assert df["country_name"].is_unique
