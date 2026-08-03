"""Automated insight generation (Milestone 12).

Turns the analytics layers below it — the M6 SQL queries and the M8 KPI engine —
into **ranked, plain-English insights** ("Movies outnumber TV Shows about 2 to 1",
"additions peaked in 2019"). This is template + rule-based **natural-language
generation**: deterministic, auditable, and — unlike an LLM — incapable of
hallucinating a number the data doesn't contain. Every sentence is rendered from a
computed value through a fixed template, and each insight is scored for
**notability** so the most interesting findings rise to the top of a "Key
Insights" panel.

The pipeline: gather the metrics once → run each generator (which applies its
threshold logic and fills a template) → rank by importance.

Run it with:  ``python -m src.analysis.insights``
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import config
from src.analysis import kpis, sql_analytics
from src.database.connection import get_connection
from src.logger import get_logger

log = get_logger(__name__)

MATURE_RATINGS = {"TV-MA", "TV-14", "R", "NC-17"}


@dataclass(frozen=True)
class Insight:
    """One generated insight: a ranked, plain-English finding with its evidence."""

    key: str
    category: str
    text: str
    importance: int      # 0-100 notability, for ranking the "Key Insights" panel
    evidence: str = ""   # short numeric backing for the claim


# ---------------------------------------------------------------------------
# Gather the inputs once (reusing the KPI engine and the SQL layer)
# ---------------------------------------------------------------------------
def _gather(conn) -> dict:
    """Collect every metric the generators need, computed once."""
    kpi = {k.key: k.value for k in kpis.compute_kpis(conn)}
    all_country_total = conn.execute(
        "SELECT COUNT(*) FROM title_countries tc JOIN countries c "
        "ON c.country_id = tc.country_id WHERE c.country_name <> 'Unknown'"
    ).fetchone()[0]
    seasons = pd.read_sql_query(
        "SELECT duration_value FROM titles WHERE duration_unit = 'Seasons'", conn
    )["duration_value"]
    one_season_share = 100.0 * (seasons == 1).mean() if len(seasons) else 0.0
    return {
        "kpi": kpi,
        "type_split": sql_analytics.run_query("content_type_split", conn),
        "growth": sql_analytics.run_query("catalog_growth_by_year", conn),
        "top_countries": sql_analytics.run_query("top_countries", conn),
        "top_genres": sql_analytics.run_query("top_genres", conn),
        "ratings": sql_analytics.run_query("rating_distribution", conn),
        "runtime_by_decade": sql_analytics.run_query("avg_movie_runtime_by_decade", conn),
        "all_country_total": all_country_total,
        "one_season_share": one_season_share,
    }


def _clamp(value: float) -> int:
    """Clamp an importance score to the 0-100 range as an int."""
    return int(max(0, min(100, round(value))))


# ---------------------------------------------------------------------------
# Insight generators (each returns one Insight; threshold logic inside)
# ---------------------------------------------------------------------------
def _composition(d: dict) -> Insight:
    kpi = d["kpi"]
    total, movies, tv = kpi["total_titles"], kpi["movies"], kpi["tv_shows"]
    movie_pct = 100 * movies / total
    ratio = movies / tv
    if movie_pct >= 60:
        posture = "movie-dominated"
    elif movie_pct <= 40:
        posture = "TV-dominated"
    else:
        posture = "fairly balanced between films and series"
    text = (f"The catalog is {posture}: Movies outnumber TV Shows about "
            f"{ratio:.1f} to 1 ({movie_pct:.0f}% of all titles).")
    # More skew from a 50/50 split is more notable.
    importance = _clamp(45 + abs(movie_pct - 50) * 2)
    return Insight("composition", "Composition", text, importance,
                   f"{movies:,} movies vs {tv:,} shows")


def _growth_peak(d: dict) -> Insight:
    g = d["growth"].dropna(subset=["year_added"]).astype({"year_added": int})
    by_year = g.set_index("year_added")["titles_added"]
    peak_year = int(by_year.idxmax())
    peak_val = int(by_year.max())
    latest_complete = int(by_year.index.max()) - 1  # final year is a partial snapshot
    latest_val = int(by_year.get(latest_complete, peak_val))
    if latest_complete <= peak_year:
        trend = "and additions have stayed high since"
    elif latest_val < peak_val:
        trend = f"then cooled to {latest_val:,} by {latest_complete}"
    else:
        trend = f"and kept climbing to {latest_val:,} by {latest_complete}"
    text = (f"Catalog additions peaked in {peak_year} with {peak_val:,} new "
            f"titles, {trend}.")
    return Insight("growth_peak", "Growth", text, 90,
                   f"peak {peak_val:,} in {peak_year}")


def _growth_cagr(d: dict) -> Insight:
    cagr = d["kpi"]["additions_cagr"]
    pace = "rapid" if cagr >= 30 else ("steady" if cagr >= 10 else "modest")
    text = (f"The catalog expanded at a {pace} {cagr:.0f}% compound annual rate "
            f"during the post-2015 build-out.")
    importance = _clamp(55 + cagr / 2)
    return Insight("growth_cagr", "Growth", text, importance, f"CAGR {cagr:.1f}%")


def _freshness(d: dict) -> Insight:
    share = d["kpi"]["new_release_share"]
    lean = "fresh new releases over deep back-catalog" if share >= 50 \
        else "back-catalog over fresh releases"
    text = (f"{share:.0f}% of titles were added within a year of their release, "
            f"so the catalog leans toward {lean}.")
    importance = _clamp(40 + abs(share - 50))
    return Insight("freshness", "Freshness", text, importance,
                   f"{share:.0f}% added <=1yr after release")


def _geography(d: dict) -> Insight:
    tc = d["top_countries"].head(3)
    names = ", ".join(tc["country_name"])
    top3_share = 100 * tc["n_titles"].sum() / d["all_country_total"]
    n_countries = int(d["kpi"]["distinct_countries"])
    concentration = "highly concentrated" if top3_share >= 50 else "broadly spread"
    text = (f"Production is {concentration}: the top three countries ({names}) "
            f"supply {top3_share:.0f}% of all country credits, though the catalog "
            f"spans {n_countries} countries in all.")
    importance = _clamp(45 + (top3_share - 33))
    return Insight("geography", "Geography", text, importance,
                   f"top-3 = {top3_share:.0f}% of {n_countries} countries")


def _international(d: dict) -> Insight:
    intl = d["kpi"]["international_share"]
    posture = "more international than American" if intl >= 50 else "US-centric"
    text = (f"{intl:.0f}% of titles are produced entirely outside the US — the "
            f"catalog is {posture}.")
    importance = _clamp(40 + abs(intl - 50))
    return Insight("international", "Geography", text, importance,
                   f"{intl:.0f}% non-US")


def _genre_leader(d: dict) -> Insight:
    leader = d["top_genres"].iloc[0]["genre_name"]
    share = d["kpi"]["top_genre_share"]
    text = (f"The most common genre is “{leader}”, tagged on {share:.0f}% of all "
            f"genre labels.")
    return Insight("genre_leader", "Genre", text, 60, f"{leader}: {share:.0f}%")


def _genre_diversity(d: dict) -> Insight:
    eff = d["kpi"]["effective_genres"]
    n = int(d["kpi"]["distinct_genres"])
    breadth = "broad" if eff >= 15 else "concentrated"
    text = (f"Across {n} genres the catalog effectively spans about {eff:.0f} "
            f"(Shannon diversity) — a {breadth} spread of content.")
    return Insight("genre_diversity", "Genre", text, 52, f"~{eff:.0f} of {n} genres")


def _ratings(d: dict) -> Insight:
    r = d["ratings"]
    total = r["n_titles"].sum()
    mature = 100 * r.loc[r["rating"].isin(MATURE_RATINGS), "n_titles"].sum() / total
    text = (f"The catalog skews adult: {mature:.0f}% of rated titles carry a "
            f"mature rating (TV-MA, TV-14, R).")
    importance = _clamp(40 + abs(mature - 50))
    return Insight("ratings", "Content", text, importance, f"{mature:.0f}% mature")


def _runtime_trend(d: dict) -> Insight:
    rd = d["runtime_by_decade"]
    peak = rd.loc[rd["avg_runtime_min"].idxmax()]  # mid-century peak, not the tiny
    late = rd.iloc[-1]                              # noisy first decade
    median = d["kpi"]["median_movie_runtime"]
    direction = "shorter" if late["avg_runtime_min"] < peak["avg_runtime_min"] else "longer"
    text = (f"The typical movie runs {median:.0f} minutes; average runtimes peaked "
            f"near {peak['avg_runtime_min']:.0f} min in the {int(peak['decade'])}s "
            f"and have trended {direction} since "
            f"(≈{late['avg_runtime_min']:.0f} min in the {int(late['decade'])}s).")
    return Insight("runtime_trend", "Format", text, 48, f"median {median:.0f} min")


def _tv_brevity(d: dict) -> Insight:
    one_season = d["one_season_share"]
    median = d["kpi"]["median_tv_seasons"]
    text = (f"Most series are short-run: {one_season:.0f}% of TV Shows have just a "
            f"single season (median {median:.0f}).")
    importance = _clamp(35 + (one_season - 50))
    return Insight("tv_brevity", "Format", text, importance,
                   f"{one_season:.0f}% single-season")


GENERATORS = [
    _composition, _growth_peak, _growth_cagr, _freshness, _geography,
    _international, _genre_leader, _genre_diversity, _ratings, _runtime_trend,
    _tv_brevity,
]


def generate_insights(conn) -> list[Insight]:
    """Run every generator and return the insights ranked by notability."""
    data = _gather(conn)
    insights = [gen(data) for gen in GENERATORS]
    insights.sort(key=lambda ins: ins.importance, reverse=True)
    log.info("Generated %d insights", len(insights))
    return insights


def key_insights(conn, n: int = 5) -> list[Insight]:
    """The top-``n`` insights by importance (for the dashboard panel)."""
    return generate_insights(conn)[:n]


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
def build_report(insights: list[Insight], top_n: int = 5) -> str:
    """Assemble the insights report: a ranked headline list, then by category."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections = [
        "# 💡 Automated Insights — Netflix Catalog",
        "",
        f"- **Generated:** {generated}",
        "- **Source:** `data/database/netflix.db` (normalized SQLite DB, Milestone 5)",
        "",
        "> Auto-generated by `src/analysis/insights.py`. Deterministic, template- "
        "and rule-based natural-language generation over the M6 SQL queries and the "
        "M8 KPI engine — every sentence is rendered from a computed value, and each "
        "insight is scored for notability so the most interesting rise to the top.",
        "",
        f"## 🔑 Key Insights (top {top_n})",
        "",
    ]
    for i, ins in enumerate(insights[:top_n], start=1):
        sections.append(f"{i}. {ins.text}")
    sections.append("")

    # Grouped by category, preserving importance order within each.
    sections += ["## All Insights by Category", ""]
    seen: list[str] = []
    for ins in insights:
        if ins.category not in seen:
            seen.append(ins.category)
    for category in seen:
        sections += [f"### {category}", ""]
        for ins in [x for x in insights if x.category == category]:
            sections.append(f"- {ins.text}  \n  _(notability {ins.importance}; {ins.evidence})_")
        sections.append("")
    return "\n".join(sections)


def save_report(insights: list[Insight], path: Path = config.INSIGHTS_REPORT) -> Path:
    """Build and write the Markdown insights report."""
    config.ensure_directories()
    path.write_text(build_report(insights), encoding="utf-8")
    log.info("Insights report written to %s", path)
    return path


def main() -> None:
    """Ensure the DB exists, generate insights, and write the report."""
    # Insight text uses curly quotes and arrows; make the console (cp1252 on
    # Windows) tolerant so the summary print never crashes. The report is UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    sql_analytics.ensure_database()
    with get_connection() as conn:
        insights = generate_insights(conn)

    out = save_report(insights)

    print("\n=== KEY INSIGHTS ===")
    for i, ins in enumerate(insights[:5], start=1):
        print(f"  {i}. [{ins.importance:>3}] {ins.text}")

    print(f"\n[OK] Insights report saved to: {out}")


if __name__ == "__main__":
    main()
