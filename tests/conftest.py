"""Shared pytest fixtures (Milestone 15).

Two flavors of fixture:

- **Synthetic** (``raw_sample`` / ``cleaned_sample``) — a tiny hand-built frame
  with every edge case the cleaning pipeline must handle, so the unit tests are
  fast and deterministic and don't depend on the real dataset.
- **Integration** (``db_conn`` / ``recommender`` / ``search_engine``) — built
  once per test session against the real SQLite database (the ETL builds it first
  if it's missing), for the query/model tests.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis import sql_analytics
from src.cleaning.pipeline import run_pipeline
from src.database.connection import get_connection
from src.recommender.engine import Recommender
from src.search.engine import SearchEngine


@pytest.fixture
def raw_sample() -> pd.DataFrame:
    """A small raw-shaped frame packed with the edge cases cleaning must fix."""
    return pd.DataFrame({
        "show_id": ["s1", "s2", "s3", "s4", "s1", "s5"],  # s1 duplicated
        "type": ["Movie", "TV Show", "Movie", "Movie", "Movie", "Movie"],
        "title": ["  Alpha  ", "Beta", "Gamma", "Delta", "Alpha (dup)", "Epsilon"],
        "director": ["Dir One", pd.NA, "Dir Two", pd.NA, "Dir One", "Dir Three"],
        "cast": ["Actor A, Actor B", "Actor C", "Actor D", pd.NA, "Actor A", "Actor E"],
        "country": ["United States", ", South Korea", "United States", pd.NA,
                    "United States", "India"],
        "date_added": ["September 25, 2021", "January 1, 2019", "March 3, 2020",
                       "not a date", "September 25, 2021", "July 4, 2021"],
        "release_year": [2020, 2018, 2019, 2017, 2020, 2021],
        "rating": ["PG-13", "TV-MA", "74 min", pd.NA, "PG-13", "R"],  # s3 leakage
        "duration": ["90 min", "2 Seasons", pd.NA, "100 min", "90 min", "120 min"],
        "listed_in": ["Dramas, Comedies", "International TV Shows", "Movies",
                      "Documentaries", "Dramas, Comedies", "Action & Adventure"],
        "description": ["d1", "d2", "d3", "d4", "d1", "d5"],
    })


@pytest.fixture
def cleaned_sample(raw_sample: pd.DataFrame) -> pd.DataFrame:
    """The synthetic frame run through the full cleaning pipeline."""
    return run_pipeline(raw_sample.copy())


@pytest.fixture(scope="session")
def db_conn():
    """A session-wide connection to the real database (built if missing)."""
    sql_analytics.ensure_database()
    with get_connection(row_factory=False) as conn:
        yield conn


@pytest.fixture(scope="session")
def recommender() -> Recommender:
    sql_analytics.ensure_database()
    with get_connection() as conn:
        return Recommender.from_connection(conn)


@pytest.fixture(scope="session")
def search_engine() -> SearchEngine:
    sql_analytics.ensure_database()
    with get_connection() as conn:
        return SearchEngine.from_connection(conn)
