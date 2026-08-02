"""Data profiling / understanding for the raw Netflix dataset (Milestone 2).

This module *observes and documents* the raw data — it does NOT modify or clean
it (that is Milestone 3). It answers the questions any analyst asks before
touching a dataset:

- How big is it (rows, columns, memory)?
- What are the column data types?
- Where are the missing values, and how severe are they?
- How unique is each column (cardinality)?
- Are there duplicate rows or duplicate IDs?
- For comma-separated columns (cast, country, genre, director), how many
  *distinct individual values* exist once we split them apart?

Every function returns a pandas object so it can be reused in notebooks, tests,
and the dashboard. ``main()`` assembles a full Markdown profile report and
saves it to ``reports/data_profile.md``.

Run it with:  ``python -m src.analysis.profiling``
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src import config
from src.logger import get_logger

log = get_logger(__name__)

# Columns that hold multiple comma-separated values in a single cell.
MULTI_VALUE_COLUMNS: tuple[str, ...] = ("director", "cast", "country", "listed_in")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_raw_data(path: Path = config.RAW_DATASET) -> pd.DataFrame:
    """Load the raw Netflix CSV into a DataFrame (no transformation applied).

    Raises
    ------
    FileNotFoundError
        If the dataset is missing, with a clear, actionable message.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Raw dataset not found at {path}. "
            "Place 'netflix_titles.csv' in data/raw/ before profiling."
        )
    log.info("Loading raw dataset from %s", path)
    df = pd.read_csv(path)
    log.info("Loaded %d rows x %d columns", df.shape[0], df.shape[1])
    return df


# ---------------------------------------------------------------------------
# Individual profiling reports (each returns a DataFrame)
# ---------------------------------------------------------------------------
def overview(df: pd.DataFrame) -> dict[str, object]:
    """Return high-level dataset facts: shape, memory, duplicate counts."""
    return {
        "n_rows": int(df.shape[0]),
        "n_columns": int(df.shape[1]),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1024**2, 2),
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_show_id": (
            int(df.duplicated(subset=["show_id"]).sum())
            if "show_id" in df.columns
            else None
        ),
    }


def column_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column summary: dtype, non-null / null counts, null %, uniqueness."""
    total = len(df)
    profile = pd.DataFrame(
        {
            "dtype": df.dtypes.astype(str),
            "non_null": df.notna().sum(),
            "nulls": df.isna().sum(),
            "null_pct": (df.isna().sum() / total * 100).round(2),
            "n_unique": df.nunique(dropna=True),
        }
    )
    profile["unique_pct"] = (profile["n_unique"] / total * 100).round(2)
    # Add up to three example non-null values per column for context.
    profile["sample_values"] = [
        _sample_values(df[col]) for col in df.columns
    ]
    return profile


def missing_report(df: pd.DataFrame) -> pd.DataFrame:
    """Columns that contain missing values, worst first."""
    total = len(df)
    report = pd.DataFrame(
        {
            "nulls": df.isna().sum(),
            "null_pct": (df.isna().sum() / total * 100).round(2),
        }
    )
    return report[report["nulls"] > 0].sort_values("nulls", ascending=False)


def multi_value_breakdown(
    df: pd.DataFrame, columns: tuple[str, ...] = MULTI_VALUE_COLUMNS
) -> pd.DataFrame:
    """Count distinct *individual* values inside comma-separated columns.

    ``df['cast']`` stores many actors per cell (e.g. "A, B, C"). Splitting on
    commas and exploding reveals the true number of distinct actors, which is
    far more meaningful than counting unique raw strings.
    """
    rows = []
    for col in columns:
        if col not in df.columns:
            continue
        exploded = _explode_multi_value(df[col])
        rows.append(
            {
                "column": col,
                "distinct_individual_values": int(exploded.nunique()),
                "total_mentions": int(exploded.shape[0]),
            }
        )
    return pd.DataFrame(rows).set_index("column")


def top_values(df: pd.DataFrame, column: str, n: int = 10) -> pd.DataFrame:
    """Most frequent individual values for a (possibly multi-value) column."""
    if column not in df.columns:
        return pd.DataFrame()
    series = (
        _explode_multi_value(df[column])
        if column in MULTI_VALUE_COLUMNS
        else df[column].dropna()
    )
    counts = series.value_counts().head(n)
    return counts.rename("count").to_frame()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _explode_multi_value(series: pd.Series, sep: str = ",") -> pd.Series:
    """Split a comma-separated column into one clean value per row."""
    return (
        series.dropna()
        .str.split(sep)
        .explode()
        .str.strip()
        .replace("", pd.NA)
        .dropna()
    )


def _sample_values(series: pd.Series, n: int = 3, max_len: int = 40) -> str:
    """Return up to ``n`` example non-null values as a short, readable string."""
    examples = series.dropna().unique()[:n]
    rendered = []
    for value in examples:
        text = str(value)
        if len(text) > max_len:
            text = text[: max_len - 1] + "…"
        rendered.append(text)
    return " · ".join(rendered) if rendered else "(all missing)"


def _md_escape(value: object) -> str:
    """Make a value safe to place inside a Markdown table cell.

    Escapes pipe characters (which otherwise start a new column) and flattens
    any newlines so a single value can never break the table layout.
    """
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _df_to_markdown(df: pd.DataFrame, index_label: str = "column") -> str:
    """Render a DataFrame as a GitHub-flavored Markdown table (no extra deps)."""
    headers = [index_label] + [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for idx, row in df.iterrows():
        cells = [_md_escape(idx)] + [_md_escape(row[c]) for c in df.columns]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
def build_markdown_report(df: pd.DataFrame) -> str:
    """Assemble the full data-profile report as a Markdown string."""
    facts = overview(df)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sections = [
        "# 📋 Data Profile Report — Netflix Titles (Raw)",
        "",
        f"- **Generated:** {generated}",
        f"- **Source:** `{config.RAW_DATASET.relative_to(config.PROJECT_ROOT)}`",
        "",
        "> Auto-generated by `src/analysis/profiling.py`. Describes the RAW "
        "dataset before any cleaning (Milestone 2).",
        "",
        "## 1. Dataset Overview",
        "",
        f"- **Rows:** {facts['n_rows']:,}",
        f"- **Columns:** {facts['n_columns']}",
        f"- **In-memory size:** {facts['memory_mb']} MB",
        f"- **Fully duplicated rows:** {facts['duplicate_rows']}",
        f"- **Duplicate `show_id` values:** {facts['duplicate_show_id']}",
        "",
        "## 2. Column Profile",
        "",
        _df_to_markdown(column_profile(df)),
        "",
        "## 3. Missing Values (worst first)",
        "",
        _df_to_markdown(missing_report(df), index_label="column"),
        "",
        "## 4. Multi-Value Column Breakdown",
        "",
        "Distinct individual values once comma-separated cells are split apart:",
        "",
        _df_to_markdown(multi_value_breakdown(df)),
        "",
        "## 5. Top Values (quick look)",
        "",
        "**Top 10 countries**",
        "",
        _df_to_markdown(top_values(df, "country"), index_label="country"),
        "",
        "**Top 10 genres (`listed_in`)**",
        "",
        _df_to_markdown(top_values(df, "listed_in"), index_label="genre"),
        "",
    ]
    return "\n".join(sections)


def save_report(df: pd.DataFrame, path: Path = config.DATA_PROFILE_REPORT) -> Path:
    """Build and write the Markdown profile report to disk."""
    config.ensure_directories()
    report = build_markdown_report(df)
    path.write_text(report, encoding="utf-8")
    log.info("Data profile report written to %s", path)
    return path


def main() -> None:
    """Entry point: load raw data, print a console summary, save the report."""
    df = load_raw_data()

    facts = overview(df)
    log.info(
        "Overview: %s rows, %s columns, %s MB, %s duplicate rows",
        f"{facts['n_rows']:,}",
        facts["n_columns"],
        facts["memory_mb"],
        facts["duplicate_rows"],
    )

    # Console-friendly summary for interactive runs.
    print("\n=== COLUMN PROFILE ===")
    print(column_profile(df).to_string())
    print("\n=== MISSING VALUES ===")
    print(missing_report(df).to_string())
    print("\n=== MULTI-VALUE BREAKDOWN ===")
    print(multi_value_breakdown(df).to_string())

    out = save_report(df)
    print(f"\n[OK] Full Markdown report saved to: {out}")


if __name__ == "__main__":
    main()
