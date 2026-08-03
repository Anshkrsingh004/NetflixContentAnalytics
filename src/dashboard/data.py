"""Cached data-access layer for the dashboard (Milestone 13).

Streamlit reruns the whole script on every interaction, so anything expensive
must be cached. This module is the single place the dashboard reaches for data:

- ``@st.cache_data`` for **serializable results** (DataFrames, metric/insight
  lists) — recomputed only when inputs change.
- ``@st.cache_resource`` for **live objects** that shouldn't be copied — the
  fitted recommender and search models (built once, reused for every query).

Every view imports from here; none of them open a database connection or fit a
model directly. That keeps the UI layer thin and the heavy lifting cached.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.analysis import insights as insights_mod
from src.analysis import kpis as kpis_mod
from src.analysis import sql_analytics
from src.database.connection import get_connection
from src.recommender.engine import Recommender, load_corpus
from src.search.engine import SearchEngine


@st.cache_resource(show_spinner=False)
def ensure_database() -> bool:
    """Build the database once if it's missing (e.g. on a fresh deploy)."""
    sql_analytics.ensure_database()
    return True


# ---------------------------------------------------------------------------
# Serializable results (@st.cache_data)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_kpis() -> list[kpis_mod.KPI]:
    ensure_database()
    with get_connection() as conn:
        return kpis_mod.compute_kpis(conn)


@st.cache_data(show_spinner=False)
def get_insights() -> list[insights_mod.Insight]:
    ensure_database()
    with get_connection() as conn:
        return insights_mod.generate_insights(conn)


@st.cache_data(show_spinner=False)
def query(name: str) -> pd.DataFrame:
    """Run a named Milestone-6 analytical query and cache the result."""
    ensure_database()
    with get_connection() as conn:
        return sql_analytics.run_query(name, conn)


@st.cache_data(show_spinner=False)
def load_titles() -> pd.DataFrame:
    """One row per title (for the filterable Explore page)."""
    ensure_database()
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM titles", conn)


@st.cache_data(show_spinner=False)
def added_by_year_type() -> pd.DataFrame:
    ensure_database()
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT year_added, type, COUNT(*) AS titles_added "
            "FROM titles WHERE year_added IS NOT NULL "
            "GROUP BY year_added, type ORDER BY year_added",
            conn,
        )


@st.cache_data(show_spinner=False)
def genre_counts() -> pd.DataFrame:
    ensure_database()
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT g.genre_name, COUNT(*) AS n_titles "
            "FROM title_genres tg JOIN genres g ON g.genre_id = tg.genre_id "
            "GROUP BY g.genre_name ORDER BY n_titles DESC",
            conn,
        )


@st.cache_data(show_spinner=False)
def country_counts() -> pd.DataFrame:
    ensure_database()
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT c.country_name, COUNT(*) AS n_titles "
            "FROM title_countries tc JOIN countries c ON c.country_id = tc.country_id "
            "WHERE c.country_name <> 'Unknown' GROUP BY c.country_name",
            conn,
        )


@st.cache_data(show_spinner=False)
def load_enriched_titles() -> pd.DataFrame:
    """Titles joined with their genre/country/director/cast strings.

    Reuses the M10 corpus loader for the denormalized metadata, then keeps every
    ``titles`` column too — so the Explore page can filter by genre/country and
    show a browsable table without re-deriving anything.
    """
    ensure_database()
    with get_connection() as conn:
        titles = pd.read_sql_query("SELECT * FROM titles", conn)
        corpus = load_corpus(conn)
    meta = corpus[["show_id", "genres", "directors", "cast", "countries"]]
    enriched = titles.merge(meta, on="show_id", how="left")
    fill = {c: "" for c in ("genres", "directors", "cast", "countries")}
    return enriched.fillna(fill)


@st.cache_data(show_spinner=False)
def title_options() -> list[str]:
    """Sorted, de-duplicated title list for the recommender's picker."""
    titles = load_titles()
    return sorted(titles["title"].dropna().unique().tolist())


# ---------------------------------------------------------------------------
# Live models (@st.cache_resource — fit once, serve every query)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Fitting recommendation model…")
def get_recommender() -> Recommender:
    ensure_database()
    with get_connection() as conn:
        return Recommender.from_connection(conn)


@st.cache_resource(show_spinner="Building search index…")
def get_search_engine() -> SearchEngine:
    ensure_database()
    with get_connection() as conn:
        return SearchEngine.from_connection(conn)
