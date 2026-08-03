"""KPI & Metrics Engine (Milestone 8).

Defines the catalog's headline **Key Performance Indicators** as reusable,
testable functions and rolls them into a single scorecard. These are the numbers
the dashboard's stat tiles (M13/M14) will surface, so each KPI is computed once,
here, and consumed everywhere else.

A note on honesty (carried from M2): this is a *catalog snapshot* with no
viewership or revenue, so every KPI describes **catalog composition, growth,
freshness, and diversity** — never popularity. Where a metric has a caveat (a
partial final snapshot year; a US-co-production definition) the KPI's description
says so rather than hiding it.

The engine layers on the stack below it: composition/age/format come from the
``titles`` table in pandas, diversity/reach from the bridge tables in SQL, and
growth **reuses the Milestone 6 `catalog_growth_by_year` query**.

Run it with:  ``python -m src.analysis.kpis``
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import config
from src.analysis import sql_analytics
from src.database.connection import get_connection
from src.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# KPI value object
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class KPI:
    """One key performance indicator, ready for a scorecard or a stat tile."""

    key: str
    label: str
    value: float
    unit: str = ""          # "%", "min", "yrs", "x", "ratio", "index", or "" (count)
    category: str = ""
    context: str = ""       # short secondary line (e.g. "69.6% of catalog")
    description: str = ""    # what it means / how it's computed / caveats

    def formatted(self) -> str:
        """Human-readable value string, unit-aware."""
        v = self.value
        if self.unit == "%":
            return f"{v:.1f}%"
        if self.unit == "min":
            return f"{v:.0f} min"
        if self.unit == "yrs":
            return f"{v:.1f} yrs"
        if self.unit == "x":
            return f"{v:.2f}×"
        if self.unit in ("ratio", "index"):
            return f"{v:.1f}"
        return f"{int(round(v)):,}"  # plain count


# ---------------------------------------------------------------------------
# Low-level helpers (each returns a plain number or Series)
# ---------------------------------------------------------------------------
def load_titles(conn) -> pd.DataFrame:
    """One row per title, for the pandas-side KPIs."""
    return pd.read_sql_query("SELECT * FROM titles", conn)


def _genre_membership_counts(conn) -> pd.Series:
    """Title-count per genre (all genres) from the bridge table."""
    df = pd.read_sql_query(
        "SELECT g.genre_name, COUNT(*) AS n "
        "FROM title_genres tg JOIN genres g ON g.genre_id = tg.genre_id "
        "GROUP BY g.genre_name",
        conn,
    )
    return df.set_index("genre_name")["n"]


def _distinct_known(conn, dim_table: str, name_col: str) -> int:
    """Count distinct dimension values, excluding the 'Unknown' sentinel."""
    return conn.execute(
        f"SELECT COUNT(*) FROM {dim_table} WHERE {name_col} <> 'Unknown'"
    ).fetchone()[0]


def _international_share(conn) -> float:
    """Percent of titles (with a known country) produced entirely outside the US.

    US co-productions count as US here — this is the share of the catalog with
    *no* US involvement, a conservative read of "international".
    """
    row = conn.execute(
        """
        WITH known AS (
            SELECT DISTINCT tc.show_id
            FROM title_countries tc JOIN countries c ON c.country_id = tc.country_id
            WHERE c.country_name <> 'Unknown'
        ),
        us AS (
            SELECT DISTINCT tc.show_id
            FROM title_countries tc JOIN countries c ON c.country_id = tc.country_id
            WHERE c.country_name = 'United States'
        )
        SELECT
            (SELECT COUNT(*) FROM known) AS known_titles,
            (SELECT COUNT(*) FROM known WHERE show_id NOT IN (SELECT show_id FROM us))
                AS non_us_titles
        """
    ).fetchone()
    known, non_us = row
    return 100.0 * non_us / known if known else 0.0


def effective_genres(counts: pd.Series) -> float:
    """Diversity as the *effective number of genres* = exp(Shannon entropy).

    Answers "how many genres does the catalog *effectively* span, weighting by
    how evenly titles are spread across them?" — a truer breadth measure than a
    raw genre count, which treats a huge and a tiny genre equally.
    """
    p = counts / counts.sum()
    entropy = float(-(p * p.apply(math.log)).sum())
    return math.exp(entropy)


# ---------------------------------------------------------------------------
# KPI computation (grouped by category)
# ---------------------------------------------------------------------------
def _scale_and_composition(df: pd.DataFrame) -> list[KPI]:
    total = len(df)
    n_movies = int((df["type"] == "Movie").sum())
    n_tv = total - n_movies
    cat = "Scale & Composition"
    return [
        KPI("total_titles", "Total titles", total, "", cat,
            "The whole catalog", "Every Movie and TV Show in the snapshot."),
        KPI("movies", "Movies", n_movies, "", cat,
            f"{100 * n_movies / total:.1f}% of catalog",
            "Titles of type Movie."),
        KPI("tv_shows", "TV Shows", n_tv, "", cat,
            f"{100 * n_tv / total:.1f}% of catalog",
            "Titles of type TV Show."),
    ]


def _growth(conn) -> list[KPI]:
    """Growth KPIs, reusing the Milestone 6 catalog-growth query."""
    growth = sql_analytics.run_query("catalog_growth_by_year", conn)
    growth = growth.dropna(subset=["year_added"]).astype({"year_added": int})
    by_year = growth.set_index("year_added")["titles_added"]

    # The final snapshot year is partial (data ends mid-2021), so the latest
    # *complete* year is the one before it — use that for YoY to avoid an
    # artificial drop.
    max_year = int(by_year.index.max())
    latest_complete = max_year - 1
    prev_year = latest_complete - 1
    added_latest = int(by_year.get(latest_complete, 0))
    added_prev = int(by_year.get(prev_year, 0))
    yoy = 100.0 * (added_latest - added_prev) / added_prev if added_prev else 0.0

    # CAGR of annual additions from the surge start (first year with >= 100
    # additions) to the latest complete year.
    surge_start = int(by_year[by_year >= 100].index.min())
    years = latest_complete - surge_start
    start_val, end_val = int(by_year[surge_start]), added_latest
    cagr = 100.0 * ((end_val / start_val) ** (1 / years) - 1) if years and start_val else 0.0

    cat = "Growth"
    return [
        KPI("added_latest_year", f"Titles added ({latest_complete})", added_latest,
            "", cat, "latest complete year",
            f"Additions in {latest_complete}; {max_year} is excluded as a partial "
            "snapshot year."),
        KPI("yoy_growth", "YoY additions growth", yoy, "%", cat,
            f"{latest_complete} vs {prev_year}",
            "Year-over-year change in titles added between the two most recent "
            "complete years."),
        KPI("additions_cagr", "Additions CAGR", cagr, "%", cat,
            f"{surge_start}→{latest_complete}",
            "Compound annual growth rate of yearly additions across the growth "
            "era — the pace of the post-2015 build-out."),
    ]


def _freshness_and_age(df: pd.DataFrame) -> list[KPI]:
    dated = df.dropna(subset=["year_added"]).copy()
    lag = dated["year_added"].astype(int) - dated["release_year"].astype(int)
    new_release_share = 100.0 * (lag <= 1).mean()
    median_lag = float(lag.median())
    as_of = int(dated["year_added"].max())
    median_age = float(as_of - df["release_year"].median())

    cat = "Freshness & Age"
    return [
        KPI("new_release_share", "New-release share", new_release_share, "%", cat,
            "added ≤ 1 yr after release",
            "Share of titles Netflix added within a year of their release — how "
            "much of the catalog is fresh rather than back-catalog."),
        KPI("median_add_lag", "Median add lag", median_lag, "yrs", cat,
            "release → Netflix",
            "Median years between a title's release and its addition."),
        KPI("median_content_age", "Median content age", median_age, "yrs", cat,
            f"as of {as_of}",
            "Median age of catalog content at the time of the snapshot "
            "(snapshot year minus release year)."),
    ]


def _diversity_and_reach(conn, genre_counts: pd.Series) -> list[KPI]:
    distinct_genres = int((genre_counts.index != "Unknown").sum())
    distinct_countries = _distinct_known(conn, "countries", "country_name")
    eff_genres = effective_genres(genre_counts)
    top_share = 100.0 * genre_counts.max() / genre_counts.sum()
    intl = _international_share(conn)

    cat = "Diversity & Reach"
    return [
        KPI("distinct_genres", "Genres covered", distinct_genres, "", cat,
            "distinct genres", "Number of distinct genres in the catalog."),
        KPI("distinct_countries", "Countries covered", distinct_countries, "", cat,
            "distinct countries",
            "Distinct producing countries (excludes the 'Unknown' sentinel)."),
        KPI("effective_genres", "Effective genres", eff_genres, "index", cat,
            "Shannon diversity",
            "exp(Shannon entropy) of the genre distribution — effective breadth "
            "weighting for how evenly titles spread across genres."),
        KPI("top_genre_share", "Top-genre share", top_share, "%", cat,
            "genre concentration",
            "Share of genre memberships held by the single largest genre — a "
            "concentration counterweight to the diversity index."),
        KPI("international_share", "International share", intl, "%", cat,
            "produced outside the US",
            "Share of titles (with a known country) with no US production."),
    ]


def _format_specifics(df: pd.DataFrame) -> list[KPI]:
    movie_runtime = df.loc[df["duration_unit"] == "Minutes", "duration_value"].median()
    tv_seasons = df.loc[df["duration_unit"] == "Seasons", "duration_value"].median()
    cat = "Format"
    return [
        KPI("median_movie_runtime", "Median movie runtime", float(movie_runtime),
            "min", cat, "typical film length",
            "Median runtime across movies (robust to the long-film tail)."),
        KPI("median_tv_seasons", "Median TV seasons", float(tv_seasons), "ratio",
            cat, "seasons per show",
            "Median number of seasons across TV Shows."),
    ]


# Order in which categories appear on the scorecard.
CATEGORY_ORDER = [
    "Scale & Composition", "Growth", "Freshness & Age",
    "Diversity & Reach", "Format",
]


def compute_kpis(conn) -> list[KPI]:
    """Compute every KPI and return them in scorecard order."""
    df = load_titles(conn)
    genre_counts = _genre_membership_counts(conn)
    kpis = [
        *_scale_and_composition(df),
        *_growth(conn),
        *_freshness_and_age(df),
        *_diversity_and_reach(conn, genre_counts),
        *_format_specifics(df),
    ]
    log.info("Computed %d KPIs across %d categories", len(kpis), len(CATEGORY_ORDER))
    return kpis


def kpis_by_category(kpis: list[KPI]) -> dict[str, list[KPI]]:
    """Group computed KPIs by their category, in ``CATEGORY_ORDER``."""
    grouped: dict[str, list[KPI]] = {c: [] for c in CATEGORY_ORDER}
    for kpi in kpis:
        grouped.setdefault(kpi.category, []).append(kpi)
    return grouped


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
# Which KPI keys make the compact "headline" strip at the top of the scorecard.
HEADLINE_KEYS = [
    "total_titles", "movies", "tv_shows", "additions_cagr",
    "new_release_share", "international_share",
]


def build_scorecard(kpis: list[KPI]) -> str:
    """Assemble the KPI scorecard as Markdown."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    by_key = {k.key: k for k in kpis}
    grouped = kpis_by_category(kpis)

    sections = [
        "# 📈 KPI Scorecard — Netflix Catalog",
        "",
        f"- **Generated:** {generated}",
        "- **Source:** `data/database/netflix.db` (normalized SQLite DB, Milestone 5)",
        "",
        "> Auto-generated by `src/analysis/kpis.py`. A *catalog* scorecard: every "
        "KPI describes composition, growth, freshness, or diversity — there is no "
        "viewership or revenue in this data, so none of these measure popularity.",
        "",
        "## Headline",
        "",
        "| KPI | Value | |",
        "| --- | --- | --- |",
    ]
    for key in HEADLINE_KEYS:
        k = by_key[key]
        sections.append(f"| {k.label} | **{k.formatted()}** | {k.context} |")
    sections.append("")

    for category in CATEGORY_ORDER:
        rows = grouped.get(category, [])
        if not rows:
            continue
        sections += [
            f"## {category}",
            "",
            "| KPI | Value | Notes |",
            "| --- | --- | --- |",
        ]
        for k in rows:
            note = k.description
            sections.append(f"| **{k.label}** | {k.formatted()} | {note} |")
        sections.append("")

    return "\n".join(sections)


def save_scorecard(kpis: list[KPI], path: Path = config.KPI_REPORT) -> Path:
    """Build and write the Markdown KPI scorecard."""
    config.ensure_directories()
    path.write_text(build_scorecard(kpis), encoding="utf-8")
    log.info("KPI scorecard written to %s", path)
    return path


def main() -> None:
    """Ensure the DB exists, compute KPIs, and save the scorecard."""
    # The report is UTF-8, but the console may be a legacy code page (cp1252 on
    # Windows) that can't encode the '→'/'≤' in KPI context strings — make stdout
    # tolerant so the summary print never crashes the run.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    sql_analytics.ensure_database()
    with get_connection() as conn:
        kpis = compute_kpis(conn)

    out = save_scorecard(kpis)

    print("\n=== KPI SCORECARD ===")
    for category in CATEGORY_ORDER:
        print(f"\n{category}")
        for k in (kpi for kpi in kpis if kpi.category == category):
            ctx = f"  ({k.context})" if k.context else ""
            print(f"  {k.label:<24} {k.formatted():>10}{ctx}")

    print(f"\n[OK] KPI scorecard saved to: {out}")


if __name__ == "__main__":
    main()
