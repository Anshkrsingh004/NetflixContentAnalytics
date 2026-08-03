"""SQL Analytics Layer (Milestone 6).

Runs a curated library of analytical SQL queries against the normalized database
(Milestone 5) and turns the results into an executive-readable Markdown report.

Each query lives as its own commented ``.sql`` file under ``sql/analytics/`` so
it can be read, run, or reused (e.g. by the M13 dashboard) on its own. This
module is the thin runner: it executes each file, returns a :class:`pandas.DataFrame`
per query, and assembles the report. Keeping the SQL in files rather than
in-lined Python strings means a reviewer can open the query, run it in any SQLite
client, and diff it independently of the code that calls it.

The queries deliberately span the analytical-SQL toolkit — many-to-many bridge
joins, ``GROUP BY``/``HAVING``, window functions (percent-of-total, running
total, partitioned ``RANK``), CTEs, and conditional-aggregation pivots.

Run it with:  ``python -m src.analysis.sql_analytics``
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.database.connection import get_connection
from src.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class AnalyticalQuery:
    """Metadata for one analytical query.

    The ``key`` doubles as the ``.sql`` filename stem, so there is a single
    source of truth linking the report entry to the file that produces it.
    """

    key: str        # stable identifier and sql/analytics/<key>.sql filename stem
    title: str      # human-readable heading for the report
    question: str   # the business question the query answers
    technique: str  # the SQL technique it showcases (for the study doc / report)


# Ordered library of analytical queries. This order is also the report order,
# grouped as: catalog composition -> growth over time -> top contributors ->
# cross-dimension analysis.
QUERIES: list[AnalyticalQuery] = [
    AnalyticalQuery(
        "content_type_split",
        "Movies vs TV Shows",
        "What is the split between Movies and TV Shows, and each type's share of the catalog?",
        "GROUP BY + window SUM(COUNT(*)) OVER () for percentage of total",
    ),
    AnalyticalQuery(
        "rating_distribution",
        "Maturity-Rating Distribution",
        "How is the catalog distributed across maturity ratings?",
        "GROUP BY + window percentage-of-total",
    ),
    AnalyticalQuery(
        "content_by_decade",
        "Movies vs TV Shows by Release Decade",
        "How many Movies vs TV Shows were released in each decade?",
        "Derived decade dimension + conditional aggregation (CASE inside SUM) to pivot",
    ),
    AnalyticalQuery(
        "catalog_growth_by_year",
        "Catalog Growth Over Time",
        "How many titles were added each year, and what is the cumulative total?",
        "Running total via SUM(COUNT(*)) OVER (ORDER BY year_added)",
    ),
    AnalyticalQuery(
        "content_freshness",
        "Content Freshness at Time of Addition",
        "How many years pass between a title's release and its addition to Netflix?",
        "CTE + CASE bucketing of a derived year-gap metric",
    ),
    AnalyticalQuery(
        "top_countries",
        "Top Producing Countries",
        "Which countries produce the most titles?",
        "Many-to-many bridge JOIN + GROUP BY + LIMIT",
    ),
    AnalyticalQuery(
        "top_genres",
        "Top Genres",
        "What are the most common genres across the catalog?",
        "Bridge JOIN + GROUP BY (counts genre memberships)",
    ),
    AnalyticalQuery(
        "top_directors",
        "Top Directors",
        "Which directors have the most titles?",
        "Bridge JOIN + GROUP BY with the 'Unknown' sentinel filtered out",
    ),
    AnalyticalQuery(
        "top_actors",
        "Top Actors",
        "Which actors appear in the most titles?",
        "Bridge JOIN + GROUP BY on the largest dimension (~36k actors)",
    ),
    AnalyticalQuery(
        "avg_movie_runtime_by_decade",
        "Average Movie Runtime by Decade",
        "Has the average movie runtime changed across decades?",
        "Filtered AVG aggregate + GROUP BY + HAVING",
    ),
    AnalyticalQuery(
        "genre_leaders_by_country",
        "Signature Genre of Each Top Country",
        "For each major producing country, what is its single most common genre?",
        "Top-N-per-group: CTE + partitioned RANK() OVER (PARTITION BY ...)",
    ),
]

# Index for quick lookup by key.
_BY_KEY: dict[str, AnalyticalQuery] = {q.key: q for q in QUERIES}


# ---------------------------------------------------------------------------
# Running queries
# ---------------------------------------------------------------------------
def read_sql(key: str) -> str:
    """Return the SQL text for a query key from ``sql/analytics/<key>.sql``."""
    path: Path = config.SQL_ANALYTICS_DIR / f"{key}.sql"
    if not path.exists():
        raise FileNotFoundError(f"No SQL file for query '{key}': {path}")
    return path.read_text(encoding="utf-8")


def run_query(key: str, conn: sqlite3.Connection) -> pd.DataFrame:
    """Execute one analytical query and return its result as a DataFrame."""
    return pd.read_sql_query(read_sql(key), conn)


def run_all(conn: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    """Execute every query in :data:`QUERIES`, keyed by query key."""
    results: dict[str, pd.DataFrame] = {}
    for q in QUERIES:
        df = run_query(q.key, conn)
        log.info("Ran query %-28s -> %3d rows", q.key, len(df))
        results[q.key] = df
    return results


def ensure_database() -> None:
    """Build the database first if it is missing or empty.

    Makes the analytics layer runnable on a fresh clone: if Milestone 5's ETL
    has not been run yet, run it now so the queries have data to hit.
    """
    needs_build = not config.DATABASE_PATH.exists()
    if not needs_build:
        with get_connection() as conn:
            try:
                needs_build = conn.execute("SELECT COUNT(*) FROM titles").fetchone()[0] == 0
            except sqlite3.OperationalError:
                needs_build = True  # schema not applied yet
    if needs_build:
        log.info("Database missing or empty; running the ETL loader first.")
        from src.database.loader import build_database

        build_database()


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
def _fmt_cell(value: object) -> str:
    """Format a single DataFrame value for a Markdown table cell.

    Handles pandas/NumPy scalars: NaN/NA -> blank, big integers get thousands
    separators (but years/decades stay bare), floats get two decimals.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (int, np.integer)):
        ivalue = int(value)
        return f"{ivalue:,}" if abs(ivalue) >= 10_000 else str(ivalue)
    if isinstance(value, (float, np.floating)):
        return f"{float(value):,.2f}"
    return str(value)


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavored Markdown table (no dependency)."""
    if df.empty:
        return "_(no rows)_"
    headers = [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in df.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(_fmt_cell(v) for v in row) + " |")
    return "\n".join(lines)


def build_report(results: dict[str, pd.DataFrame]) -> str:
    """Assemble the full SQL-analytics report as Markdown."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections = [
        "# 📊 SQL Analytics — Netflix Catalog Insights",
        "",
        f"- **Generated:** {generated}",
        "- **Source:** `data/database/netflix.db` — the normalized SQLite "
        "database from Milestone 5",
        "",
        "> Auto-generated by `src/analysis/sql_analytics.py`. Each section runs a "
        "standalone query from `sql/analytics/` against the normalized database "
        "and reports the result.",
        "",
        f"**{len(QUERIES)} analytical queries** spanning catalog composition, "
        "growth over time, top contributors, and cross-dimension analysis.",
        "",
        "---",
        "",
    ]
    for i, q in enumerate(QUERIES, start=1):
        df = results[q.key]
        sections += [
            f"## {i}. {q.title}",
            "",
            f"**Question:** {q.question}  ",
            f"**SQL technique:** {q.technique}  ",
            f"**Query file:** `sql/analytics/{q.key}.sql`",
            "",
            _df_to_markdown(df),
            "",
        ]
    return "\n".join(sections)


def save_report(
    results: dict[str, pd.DataFrame], path: Path = config.SQL_ANALYTICS_REPORT
) -> Path:
    """Build and write the Markdown SQL-analytics report."""
    config.ensure_directories()
    path.write_text(build_report(results), encoding="utf-8")
    log.info("SQL analytics report written to %s", path)
    return path


def main() -> None:
    """Ensure the DB exists, run every query, and save the report."""
    ensure_database()
    with get_connection(row_factory=False) as conn:
        results = run_all(conn)

    out = save_report(results)

    print("\n=== SQL ANALYTICS SUMMARY ===")
    for q in QUERIES:
        print(f"  {q.key:<28} {len(results[q.key]):>3} rows")

    # A couple of headline numbers so the run is self-verifying at a glance.
    split = results["content_type_split"]
    print("\nCatalog composition:")
    for _, r in split.iterrows():
        print(f"  {r['type']:<8} {int(r['n_titles']):>5,}  ({r['pct_of_catalog']:.1f}%)")

    print(f"\n[OK] SQL analytics report saved to: {out}")


if __name__ == "__main__":
    main()
