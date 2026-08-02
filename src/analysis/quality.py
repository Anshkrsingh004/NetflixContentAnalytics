"""Automated data-quality assessment and reporting (Milestone 4).

Scores a dataset across four widely-used data-quality dimensions and combines
them into a single **Data Quality Score** (0-100). The report compares the RAW
dataset against the CLEANED dataset so the value added by the cleaning pipeline
(Milestone 3) is quantified, not just asserted.

Dimensions
----------
- **Completeness** : share of non-null cells.
- **Validity**     : share of values that satisfy domain rules (e.g. `type` is
                     Movie/TV Show, `rating` is not a stray duration).
- **Uniqueness**   : share of rows that are not duplicates.
- **Consistency**  : cross-field agreement (duration unit matches title type).
                     Only computable once the data is cleaned; N/A on raw.

The composite score is a weighted average of the *available* dimensions.

Run it with:  ``python -m src.analysis.quality``
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src import config
from src.analysis.profiling import load_raw_data
from src.cleaning.pipeline import run_pipeline
from src.logger import get_logger

log = get_logger(__name__)

VALID_TYPES = {"Movie", "TV Show"}
# Weights for the composite score (renormalized over available dimensions).
DIMENSION_WEIGHTS = {
    "completeness": 0.40,
    "validity": 0.30,
    "uniqueness": 0.20,
    "consistency": 0.10,
}


# ---------------------------------------------------------------------------
# Individual metrics
# ---------------------------------------------------------------------------
def completeness_by_column(df: pd.DataFrame) -> pd.Series:
    """Per-column completeness as a percentage of non-null values."""
    return (df.notna().sum() / len(df) * 100).round(2)


def completeness_score(df: pd.DataFrame) -> float:
    """Overall completeness: percent of non-null cells across the whole table."""
    total_cells = df.shape[0] * df.shape[1]
    non_null = int(df.notna().sum().sum())
    return round(non_null / total_cells * 100, 2) if total_cells else 0.0


def duplicate_percentage(df: pd.DataFrame) -> float:
    """Percentage of rows that are exact duplicates of an earlier row."""
    return round(df.duplicated().mean() * 100, 2) if len(df) else 0.0


def uniqueness_score(df: pd.DataFrame) -> float:
    """100 minus the duplicate-row percentage."""
    return round(100 - duplicate_percentage(df), 2)


def validity_rules(df: pd.DataFrame) -> dict[str, float]:
    """Compute per-rule pass rates (%) for the domain rules that apply.

    Only rules whose required columns exist are evaluated, so the same function
    works on both the raw and cleaned datasets.
    """
    rules: dict[str, float] = {}
    if "type" in df:
        rules["type_in_domain"] = df["type"].isin(VALID_TYPES).mean() * 100
    if "rating" in df:
        # A valid rating must NOT look like a duration ("74 min") — the raw
        # data has 3 such leaked values; the cleaned data has none.
        looks_like_duration = df["rating"].astype("string").str.match(
            r"^\d+\s*min$", case=False, na=False
        )
        rules["rating_not_duration"] = (~looks_like_duration).mean() * 100
    if "release_year" in df:
        rules["release_year_in_range"] = df["release_year"].between(1900, 2025).mean() * 100
    if "duration_value" in df:
        rules["duration_value_positive"] = (df["duration_value"].fillna(0) > 0).mean() * 100
    return {k: round(v, 2) for k, v in rules.items()}


def validity_score(df: pd.DataFrame) -> float | None:
    """Mean pass rate across applicable validity rules (None if none apply)."""
    rules = validity_rules(df)
    return round(sum(rules.values()) / len(rules), 2) if rules else None


def consistency_score(df: pd.DataFrame) -> float | None:
    """Percent of rows where duration unit matches the title type.

    Movies should be measured in Minutes, TV Shows in Seasons. Requires the
    cleaned ``duration_unit`` column, so returns None on the raw dataset.
    """
    if "duration_unit" not in df or "type" not in df:
        return None
    expected = df["type"].map({"Movie": "Minutes", "TV Show": "Seasons"})
    return round((df["duration_unit"] == expected).mean() * 100, 2)


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------
def quality_dimensions(df: pd.DataFrame) -> dict[str, float | None]:
    """Return all four dimension scores (values may be None if N/A)."""
    return {
        "completeness": completeness_score(df),
        "validity": validity_score(df),
        "uniqueness": uniqueness_score(df),
        "consistency": consistency_score(df),
    }


def data_quality_score(df: pd.DataFrame) -> float:
    """Weighted average of available dimensions, renormalized (0-100)."""
    dims = quality_dimensions(df)
    weighted_sum = 0.0
    weight_total = 0.0
    for name, weight in DIMENSION_WEIGHTS.items():
        value = dims.get(name)
        if value is not None:
            weighted_sum += value * weight
            weight_total += weight
    return round(weighted_sum / weight_total, 2) if weight_total else 0.0


def grade(score: float) -> str:
    """Map a 0-100 score to a letter grade for at-a-glance interpretation."""
    thresholds = [(97, "A+"), (93, "A"), (90, "A-"), (85, "B"),
                  (75, "C"), (65, "D")]
    for cutoff, letter in thresholds:
        if score >= cutoff:
            return letter
    return "F"


def assess(df: pd.DataFrame) -> dict[str, object]:
    """Bundle the headline quality metrics for one dataset."""
    score = data_quality_score(df)
    return {
        "rows": len(df),
        "columns": df.shape[1],
        "missing_cells_pct": round(100 - completeness_score(df), 2),
        "duplicate_pct": duplicate_percentage(df),
        "dimensions": quality_dimensions(df),
        "score": score,
        "grade": grade(score),
    }


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
def _fmt(value: float | None) -> str:
    """Format a possibly-None metric for a Markdown cell."""
    return "N/A" if value is None else f"{value:.2f}"


def build_quality_report(raw: pd.DataFrame, clean: pd.DataFrame) -> str:
    """Assemble the raw-vs-clean data-quality report as Markdown."""
    raw_a, clean_a = assess(raw), assess(clean)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Headline table
    headline = [
        "| Metric | Raw | Cleaned |",
        "| --- | --- | --- |",
        f"| Rows | {raw_a['rows']:,} | {clean_a['rows']:,} |",
        f"| Columns | {raw_a['columns']} | {clean_a['columns']} |",
        f"| Missing cells % | {raw_a['missing_cells_pct']:.2f}% | {clean_a['missing_cells_pct']:.2f}% |",
        f"| Duplicate rows % | {raw_a['duplicate_pct']:.2f}% | {clean_a['duplicate_pct']:.2f}% |",
        f"| **Data Quality Score** | **{raw_a['score']:.2f} ({raw_a['grade']})** "
        f"| **{clean_a['score']:.2f} ({clean_a['grade']})** |",
    ]

    # Dimension breakdown
    dims = ["completeness", "validity", "uniqueness", "consistency"]
    dim_rows = ["| Dimension | Raw | Cleaned |", "| --- | --- | --- |"]
    for d in dims:
        dim_rows.append(
            f"| {d.capitalize()} | {_fmt(raw_a['dimensions'][d])} "
            f"| {_fmt(clean_a['dimensions'][d])} |"
        )

    # Per-column completeness (union of columns)
    raw_comp = completeness_by_column(raw)
    clean_comp = completeness_by_column(clean)
    all_cols = list(dict.fromkeys(list(raw.columns) + list(clean.columns)))
    comp_rows = ["| Column | Raw % | Cleaned % |", "| --- | --- | --- |"]
    for col in all_cols:
        r = f"{raw_comp[col]:.2f}" if col in raw_comp else "—"
        c = f"{clean_comp[col]:.2f}" if col in clean_comp else "—"
        comp_rows.append(f"| `{col}` | {r} | {c} |")

    improvement = clean_a["score"] - raw_a["score"]
    sections = [
        "# 🧪 Data Quality Report — Netflix Titles",
        "",
        f"- **Generated:** {generated}",
        "- **Compares:** raw `data/raw/netflix_titles.csv` vs. cleaned output of "
        "the Milestone 3 pipeline",
        "",
        "> Auto-generated by `src/analysis/quality.py`. Scores four dimensions "
        "(completeness, validity, uniqueness, consistency) into a composite "
        "0-100 Data Quality Score.",
        "",
        "## 1. Headline",
        "",
        *headline,
        "",
        f"**Cleaning lifted the Data Quality Score by "
        f"{improvement:+.2f} points** (raw {raw_a['score']:.2f} → "
        f"clean {clean_a['score']:.2f}).",
        "",
        "## 2. Dimension Breakdown",
        "",
        *dim_rows,
        "",
        "_Consistency is N/A on raw data because it needs the cleaned "
        "`duration_unit` column._",
        "",
        "## 3. Per-Column Completeness",
        "",
        *comp_rows,
        "",
        "## 4. How the Score Is Computed",
        "",
        "Composite = weighted average of available dimensions "
        "(completeness 40%, validity 30%, uniqueness 20%, consistency 10%), "
        "renormalized when a dimension is N/A.",
        "",
    ]
    return "\n".join(sections)


def save_quality_report(
    raw: pd.DataFrame, clean: pd.DataFrame, path: Path = config.DATA_QUALITY_REPORT
) -> Path:
    """Build and write the Markdown quality report."""
    config.ensure_directories()
    path.write_text(build_quality_report(raw, clean), encoding="utf-8")
    log.info("Data quality report written to %s", path)
    return path


def main() -> None:
    """Load raw, clean it, score both, save the comparison report."""
    raw = load_raw_data()
    clean = run_pipeline(raw.copy())

    raw_a, clean_a = assess(raw), assess(clean)
    log.info("Raw   Data Quality Score: %.2f (%s)", raw_a["score"], raw_a["grade"])
    log.info("Clean Data Quality Score: %.2f (%s)", clean_a["score"], clean_a["grade"])

    print("\n=== DATA QUALITY: RAW vs CLEAN ===")
    print(f"  Missing cells %: {raw_a['missing_cells_pct']:.2f}  ->  "
          f"{clean_a['missing_cells_pct']:.2f}")
    print(f"  Score          : {raw_a['score']:.2f} ({raw_a['grade']})  ->  "
          f"{clean_a['score']:.2f} ({clean_a['grade']})")

    out = save_quality_report(raw, clean)
    print(f"\n[OK] Quality report saved to: {out}")


if __name__ == "__main__":
    main()
