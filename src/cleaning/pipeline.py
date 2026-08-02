"""End-to-end data-cleaning pipeline orchestrator (Milestone 3).

Chains the individual steps in ``cleaners.py`` in the correct order, validates
the result with ``validation.py``, and writes the clean dataset to
``data/processed/netflix_clean.csv``.

Run it with:  ``python -m src.cleaning.pipeline``
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.analysis.profiling import load_raw_data  # reuse the loader (DRY)
from src.cleaning import cleaners
from src.cleaning.validation import validate_clean_data
from src.logger import get_logger

log = get_logger(__name__)

# Column order for the output file: identity -> attributes -> derived.
CLEAN_COLUMN_ORDER = [
    "show_id", "type", "title", "director", "cast", "country",
    "date_added", "year_added", "month_added",
    "release_year", "rating",
    "duration", "duration_value", "duration_unit",
    "listed_in", "primary_genre", "primary_country",
    "description",
]


def run_pipeline(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Run all cleaning steps in order and validate the result.

    Parameters
    ----------
    df:
        Optional raw DataFrame. If ``None``, the raw CSV is loaded from disk.
        Accepting an injected DataFrame makes the pipeline easy to unit-test.
    """
    if df is None:
        df = load_raw_data()

    log.info("=== Cleaning pipeline START (%d rows) ===", len(df))

    # Order matters: whitespace first (so parsing is reliable), leakage fix
    # before duration/rating steps, fills before deriving primary_* columns.
    df = cleaners.strip_whitespace(df)
    df = cleaners.remove_duplicates(df)
    df = cleaners.normalize_multivalue_columns(df)
    df = cleaners.fix_rating_duration_leakage(df)
    df = cleaners.split_duration(df)
    df = cleaners.clean_rating(df)
    df = cleaners.parse_date_added(df)
    df = cleaners.fill_missing_values(df)
    df = cleaners.add_primary_values(df)

    # Reorder columns for a tidy output (ignore any that are unexpectedly absent).
    ordered = [c for c in CLEAN_COLUMN_ORDER if c in df.columns]
    df = df[ordered]

    validate_clean_data(df)
    log.info("=== Cleaning pipeline DONE (%d rows x %d cols) ===", *df.shape)
    return df


def save_clean_data(df: pd.DataFrame, path: Path = config.CLEAN_DATASET) -> Path:
    """Write the cleaned DataFrame to CSV (UTF-8, no index)."""
    config.ensure_directories()
    df.to_csv(path, index=False, encoding="utf-8")
    log.info("Clean dataset written to %s", path)
    return path


def summarize(raw: pd.DataFrame, clean: pd.DataFrame) -> str:
    """Return a short before/after summary string for the console."""
    lines = [
        "\n=== CLEANING SUMMARY ===",
        f"Rows      : {len(raw):,} -> {len(clean):,}",
        f"Columns   : {raw.shape[1]} -> {clean.shape[1]} "
        f"(+{clean.shape[1] - raw.shape[1]} derived)",
        f"Nulls (director/country/cast): "
        f"{int(raw[['director','country','cast']].isna().sum().sum())} -> "
        f"{int(clean[['director','country','cast']].isna().sum().sum())}",
        f"date_added dtype: {raw['date_added'].dtype} -> {clean['date_added'].dtype}",
        f"New columns: "
        f"{sorted(set(clean.columns) - set(raw.columns))}",
    ]
    return "\n".join(lines)


def main() -> None:
    """Entry point: load raw, clean, validate, save, and print a summary."""
    raw = load_raw_data()
    clean = run_pipeline(raw.copy())
    out = save_clean_data(clean)
    print(summarize(raw, clean))
    print(f"\n[OK] Clean dataset saved to: {out}")


if __name__ == "__main__":
    main()
