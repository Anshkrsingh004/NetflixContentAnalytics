"""Individual, composable cleaning steps for the Netflix dataset (Milestone 3).

Each function is a *pure* transformation: it takes a DataFrame, returns a new
DataFrame, and never mutates its input (we always ``.copy()`` first). Keeping
each step small and independent makes the pipeline easy to read, unit-test, and
reorder. Orchestration lives in ``pipeline.py``; validation in ``validation.py``.

Every step logs what it changed, so a run produces an auditable trail of exactly
how the raw data became the clean data.
"""

from __future__ import annotations

import pandas as pd

from src.logger import get_logger

log = get_logger(__name__)

# Columns filled with this sentinel when missing (see fill_missing_values).
UNKNOWN = "Unknown"
# Rating used when a title's rating is missing or unrecoverable (Not Rated).
DEFAULT_RATING = "NR"
# Comma-separated columns that hold multiple values per cell.
MULTI_VALUE_COLUMNS = ("director", "cast", "country", "listed_in")


def strip_whitespace(df: pd.DataFrame) -> pd.DataFrame:
    """Trim leading/trailing whitespace from every text column.

    Also converts any resulting empty strings to ``NA`` so that "  " is treated
    as missing rather than as a real (blank) value.
    """
    df = df.copy()
    text_cols = df.select_dtypes(include="object").columns
    for col in text_cols:
        df[col] = df[col].str.strip().replace("", pd.NA)
    log.info("Stripped whitespace on %d text column(s)", len(text_cols))
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Drop fully-duplicated rows and any repeated ``show_id`` (keep first)."""
    df = df.copy()
    before = len(df)
    df = df.drop_duplicates()
    if "show_id" in df.columns:
        df = df.drop_duplicates(subset="show_id", keep="first")
    removed = before - len(df)
    log.info("Removed %d duplicate row(s)", removed)
    return df


def _normalize_list_string(value: object) -> object:
    """Clean one comma-separated cell: strip tokens, drop empties, rejoin.

    ``", South Korea"`` -> ``"South Korea"`` and ``"A,  , B"`` -> ``"A, B"``.
    Returns ``NA`` if nothing is left, so it can be filled downstream.
    """
    if pd.isna(value):
        return pd.NA
    parts = [p.strip() for p in str(value).split(",")]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else pd.NA


def normalize_multivalue_columns(
    df: pd.DataFrame, columns: tuple[str, ...] = MULTI_VALUE_COLUMNS
) -> pd.DataFrame:
    """Normalize comma-separated columns (remove empty/leading/trailing tokens).

    Fixes real dirty rows such as ``country = ", South Korea"`` that would
    otherwise yield an empty first value. Runs before missing-value filling so
    any cell that becomes empty is treated as missing.
    """
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = df[col].map(_normalize_list_string)
    log.info(
        "Normalized %d multi-value column(s) (removed empty/leading commas)",
        len(columns),
    )
    return df


def fix_rating_duration_leakage(df: pd.DataFrame) -> pd.DataFrame:
    """Repair rows where a duration value leaked into the ``rating`` column.

    In the raw data, 3 rows (Louis C.K. specials) store a value like ``"74 min"``
    in ``rating`` and leave ``duration`` null — the data is shifted one column
    over. We move the value back into ``duration`` and set ``rating`` to ``NR``.
    Must run BEFORE ``split_duration`` and rating cleaning.
    """
    df = df.copy()
    leaked = df["rating"].str.match(r"^\d+\s*min$", case=False, na=False)
    n = int(leaked.sum())
    if n:
        df.loc[leaked, "duration"] = df.loc[leaked, "rating"]
        df.loc[leaked, "rating"] = DEFAULT_RATING
        log.info("Fixed rating/duration leakage in %d row(s)", n)
    return df


def split_duration(df: pd.DataFrame) -> pd.DataFrame:
    """Split the dual-unit ``duration`` string into a value + a unit.

    ``"90 min"`` -> (90, "Minutes");  ``"2 Seasons"`` -> (2, "Seasons").
    Movies are measured in minutes, TV shows in seasons, so a single numeric
    column cannot represent both. We add:
      - ``duration_value`` : nullable integer (Int64)
      - ``duration_unit``  : "Minutes" or "Seasons"
    The original ``duration`` string is kept for traceability.
    """
    df = df.copy()
    extracted = df["duration"].str.extract(r"(?P<value>\d+)\s*(?P<unit>[A-Za-z]+)")
    df["duration_value"] = pd.to_numeric(extracted["value"], errors="coerce").astype("Int64")
    df["duration_unit"] = (
        extracted["unit"]
        .str.lower()
        .map({"min": "Minutes", "season": "Seasons", "seasons": "Seasons"})
    )
    log.info(
        "Split duration -> %d in Minutes, %d in Seasons",
        int((df["duration_unit"] == "Minutes").sum()),
        int((df["duration_unit"] == "Seasons").sum()),
    )
    return df


def clean_rating(df: pd.DataFrame) -> pd.DataFrame:
    """Fill any remaining missing ratings with the 'Not Rated' sentinel."""
    df = df.copy()
    n = int(df["rating"].isna().sum())
    if n:
        df["rating"] = df["rating"].fillna(DEFAULT_RATING)
        log.info("Filled %d missing rating(s) with '%s'", n, DEFAULT_RATING)
    return df


def parse_date_added(df: pd.DataFrame) -> pd.DataFrame:
    """Parse ``date_added`` text into a real datetime and derive date parts.

    Format is ``"September 25, 2021"`` (``%B %d, %Y``). Unparseable/missing
    values become ``NaT``. Adds nullable-integer ``year_added`` / ``month_added``
    for time-series analysis.
    """
    df = df.copy()
    df["date_added"] = pd.to_datetime(
        df["date_added"], format="%B %d, %Y", errors="coerce"
    )
    df["year_added"] = df["date_added"].dt.year.astype("Int64")
    df["month_added"] = df["date_added"].dt.month.astype("Int64")
    n_unparsed = int(df["date_added"].isna().sum())
    log.info("Parsed date_added (%d remain missing/NaT)", n_unparsed)
    return df


def fill_missing_values(
    df: pd.DataFrame,
    columns: tuple[str, ...] = ("director", "cast", "country"),
    value: str = UNKNOWN,
) -> pd.DataFrame:
    """Fill missing values in high-null text columns with an explicit sentinel.

    We keep the rows (dropping ~30% for null ``director`` would bias every
    statistic) and mark the gap honestly as ``"Unknown"`` rather than guessing.
    """
    df = df.copy()
    for col in columns:
        n = int(df[col].isna().sum())
        if n:
            df[col] = df[col].fillna(value)
            log.info("Filled %d missing '%s' value(s) with '%s'", n, col, value)
    return df


def _first_token(value: object) -> str:
    """Return the first non-empty comma-separated token, else the sentinel."""
    if pd.isna(value):
        return UNKNOWN
    for part in str(value).split(","):
        part = part.strip()
        if part:
            return part
    return UNKNOWN


def add_primary_values(df: pd.DataFrame) -> pd.DataFrame:
    """Derive single-value helper columns from multi-value columns.

    ``primary_country`` / ``primary_genre`` take the first *non-empty* listed
    value (falling back to ``"Unknown"``), which is convenient for simple
    grouping, maps, and dashboard filters. The full comma-separated columns are
    retained for normalization in Milestone 5.
    """
    df = df.copy()
    df["primary_country"] = df["country"].map(_first_token)
    df["primary_genre"] = df["listed_in"].map(_first_token)
    log.info("Added derived columns: primary_country, primary_genre")
    return df
