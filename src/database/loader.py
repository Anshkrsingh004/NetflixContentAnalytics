"""Automated ETL: build the normalized SQLite database from cleaned data (M5).

Reads ``data/processed/netflix_clean.csv`` (regenerating it via the cleaning
pipeline if it is missing), applies ``sql/schema.sql``, then loads:

- the ``titles`` entity table (one row per show), and
- for each multi-value attribute (genre, country, director, cast): a dimension
  table of distinct values plus a bridge table linking titles to those values.

Run it with:  ``python -m src.database.loader``
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.database.connection import get_connection
from src.logger import get_logger

log = get_logger(__name__)

# Columns loaded straight into the titles entity table.
TITLE_COLUMNS = [
    "show_id", "type", "title", "date_added", "year_added", "month_added",
    "release_year", "rating", "duration_value", "duration_unit", "description",
]

# (source column, dimension table, id column, name column, bridge table)
DIMENSION_SPECS = [
    ("listed_in", "genres", "genre_id", "genre_name", "title_genres"),
    ("country", "countries", "country_id", "country_name", "title_countries"),
    ("director", "directors", "director_id", "director_name", "title_directors"),
    ("cast", "actors", "actor_id", "actor_name", "title_cast"),
]

ALL_TABLES = [
    "titles", "genres", "countries", "directors", "actors",
    "title_genres", "title_countries", "title_directors", "title_cast",
]


def _bind(value: object) -> object:
    """Coerce a pandas/NumPy scalar into a value sqlite3 can bind.

    Handles NaN/NA -> None and NumPy int/float/Timestamp -> native Python types,
    which sqlite3 cannot bind directly.
    """
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return value


def load_clean_dataframe() -> pd.DataFrame:
    """Load the cleaned dataset, building it first if it does not exist."""
    if not config.CLEAN_DATASET.exists():
        log.info("Clean dataset not found; running cleaning pipeline first.")
        from src.cleaning.pipeline import run_pipeline, save_clean_data
        save_clean_data(run_pipeline())

    df = pd.read_csv(config.CLEAN_DATASET)
    # CSV loses the nullable-integer dtype; restore it for clean DB values.
    for col in ("year_added", "month_added", "duration_value"):
        if col in df.columns:
            df[col] = df[col].astype("Int64")
    log.info("Loaded clean dataset for ETL: %d rows", len(df))
    return df


def apply_schema(conn: sqlite3.Connection) -> None:
    """Execute schema.sql to (re)create all tables and indexes."""
    conn.executescript(config.SCHEMA_SQL.read_text(encoding="utf-8"))
    log.info("Applied schema from %s", config.SCHEMA_SQL)


def insert_titles(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Insert the one-row-per-title entity records."""
    placeholders = ", ".join(["?"] * len(TITLE_COLUMNS))
    columns = ", ".join(TITLE_COLUMNS)
    rows = [
        tuple(_bind(v) for v in record)
        for record in df[TITLE_COLUMNS].itertuples(index=False, name=None)
    ]
    conn.executemany(
        f"INSERT INTO titles ({columns}) VALUES ({placeholders})", rows
    )
    log.info("Inserted %d titles", len(rows))
    return len(rows)


def load_dimension_and_bridge(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    source_col: str,
    dim_table: str,
    id_col: str,
    name_col: str,
    bridge_table: str,
) -> tuple[int, int]:
    """Populate one dimension table and its bridge from a multi-value column."""
    # Explode "A, B, C" into one (show_id, value) pair per value.
    pairs = df[["show_id", source_col]].copy()
    pairs[source_col] = pairs[source_col].str.split(",")
    pairs = pairs.explode(source_col)
    pairs[source_col] = pairs[source_col].str.strip()
    pairs = pairs[pairs[source_col].notna() & (pairs[source_col] != "")]

    # 1) Insert the distinct values into the dimension table.
    distinct_values = sorted(pairs[source_col].unique())
    conn.executemany(
        f"INSERT INTO {dim_table} ({name_col}) VALUES (?)",
        [(value,) for value in distinct_values],
    )

    # 2) Map value -> generated id, then insert the bridge links.
    id_map = {
        name: row_id
        for name, row_id in conn.execute(f"SELECT {name_col}, {id_col} FROM {dim_table}")
    }
    bridge_rows = [
        (show_id, id_map[value])
        for show_id, value in zip(pairs["show_id"], pairs[source_col])
    ]
    conn.executemany(
        f"INSERT OR IGNORE INTO {bridge_table} (show_id, {id_col}) VALUES (?, ?)",
        bridge_rows,
    )
    log.info(
        "Loaded %-16s %5d distinct -> %6d links (%s)",
        dim_table + ":", len(distinct_values), len(bridge_rows), bridge_table,
    )
    return len(distinct_values), len(bridge_rows)


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return row counts for every table (for verification/reporting)."""
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ALL_TABLES
    }


def build_database(db_path: Path = config.DATABASE_PATH) -> Path:
    """Full ETL: load clean data, apply schema, populate all tables."""
    df = load_clean_dataframe()
    log.info("=== Building database at %s ===", db_path)
    with get_connection(db_path) as conn:
        apply_schema(conn)
        insert_titles(conn, df)
        for spec in DIMENSION_SPECS:
            load_dimension_and_bridge(conn, df, *spec)
    log.info("=== Database build complete ===")
    return db_path


def main() -> None:
    """Build the database and print a verification summary."""
    build_database()
    with get_connection(row_factory=True) as conn:
        counts = table_counts(conn)
        print("\n=== TABLE ROW COUNTS ===")
        for table, n in counts.items():
            print(f"  {table:<18} {n:>7,}")

        print("\n=== Sanity check: top 5 countries by #titles ===")
        top = conn.execute(
            """
            SELECT c.country_name, COUNT(*) AS n_titles
            FROM title_countries tc
            JOIN countries c ON c.country_id = tc.country_id
            GROUP BY c.country_name
            ORDER BY n_titles DESC
            LIMIT 5
            """
        ).fetchall()
        for row in top:
            print(f"  {row['country_name']:<20} {row['n_titles']:>5}")

        # Referential-integrity check: should return no rows.
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        print(f"\nForeign-key violations: {len(violations)} (expected 0)")

    print(f"\n[OK] Database built at: {config.DATABASE_PATH}")


if __name__ == "__main__":
    main()
