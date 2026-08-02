"""Post-cleaning data validation (Milestone 3).

After the pipeline runs, we assert a set of invariants the clean dataset must
satisfy. Validation is split into two severities:

- **Critical** checks raise :class:`DataValidationError` -the data is unusable
  if they fail (e.g. duplicate primary keys), so we stop immediately.
- **Soft** checks only log a warning -they flag things worth knowing without
  aborting the run (e.g. some ``date_added`` values remained NaT).

This "fail fast, but only on what matters" approach is how production data
pipelines prevent silently shipping broken data downstream.
"""

from __future__ import annotations

import pandas as pd

from src.logger import get_logger

log = get_logger(__name__)

VALID_TYPES = {"Movie", "TV Show"}
VALID_DURATION_UNITS = {"Minutes", "Seasons"}
NO_NULL_COLUMNS = ("show_id", "type", "title", "director", "cast", "country",
                   "rating", "duration_value", "duration_unit",
                   "primary_country", "primary_genre")


class DataValidationError(Exception):
    """Raised when the cleaned dataset fails a critical validation check."""


def validate_clean_data(df: pd.DataFrame) -> dict[str, bool]:
    """Validate the cleaned DataFrame; raise on any critical failure.

    Returns
    -------
    dict[str, bool]
        A check-name -> passed mapping (useful for tests and reporting).
    """
    results: dict[str, bool] = {}
    critical_failures: list[str] = []

    def check(name: str, passed: bool, *, critical: bool, detail: str = "") -> None:
        results[name] = passed
        if passed:
            log.info("PASS  %s", name)
        elif critical:
            critical_failures.append(f"{name} - {detail}")
            log.error("FAIL  %s - %s", name, detail)
        else:
            log.warning("WARN  %s - %s", name, detail)

    # --- Critical checks ---------------------------------------------------
    check(
        "show_id_unique",
        df["show_id"].is_unique and df["show_id"].notna().all(),
        critical=True,
        detail="show_id must be unique and non-null",
    )

    invalid_types = set(df["type"].dropna().unique()) - VALID_TYPES
    check(
        "type_values_valid",
        not invalid_types,
        critical=True,
        detail=f"unexpected type values: {invalid_types}",
    )

    invalid_units = set(df["duration_unit"].dropna().unique()) - VALID_DURATION_UNITS
    check(
        "duration_unit_valid",
        not invalid_units,
        critical=True,
        detail=f"unexpected duration units: {invalid_units}",
    )

    check(
        "duration_value_positive",
        bool((df["duration_value"].dropna() > 0).all()),
        critical=True,
        detail="all duration_value entries must be > 0",
    )

    missing_no_null = [c for c in NO_NULL_COLUMNS if c in df and df[c].isna().any()]
    check(
        "no_nulls_in_key_columns",
        not missing_no_null,
        critical=True,
        detail=f"unexpected nulls in: {missing_no_null}",
    )

    # --- Soft checks -------------------------------------------------------
    check(
        "release_year_in_range",
        bool(df["release_year"].between(1900, 2025).all()),
        critical=False,
        detail="some release_year values fall outside 1900-2025",
    )

    n_nat = int(df["date_added"].isna().sum())
    check(
        "date_added_mostly_parsed",
        n_nat == 0,
        critical=False,
        detail=f"{n_nat} date_added value(s) are NaT (were missing in raw data)",
    )

    if critical_failures:
        raise DataValidationError(
            "Cleaned data failed critical validation:\n  - "
            + "\n  - ".join(critical_failures)
        )

    log.info("Validation complete: %d/%d checks passed",
             sum(results.values()), len(results))
    return results
