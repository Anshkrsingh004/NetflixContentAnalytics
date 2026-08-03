"""Exploratory Data Analysis (Milestone 7).

Turns the cleaned, normalized catalog into visual, quantified understanding:
univariate distributions, temporal trends, an outlier analysis, and the (few)
numeric correlations the data supports. Every analysis returns a DataFrame and
every chart returns a :class:`matplotlib.figure.Figure`, so the same code powers
three consumers: the ``notebooks/eda.ipynb`` narrative, the generated
``reports/eda_report.md``, and later the dashboard.

Design choices worth defending:
- EDA works in **pandas** on the ``titles`` entity table (the classic EDA
  workflow), and **reuses the Milestone 6 SQL layer** for the ranking charts
  (top genres/countries) — it builds on the stack below it rather than
  re-deriving those aggregates.
- Charts use a **colorblind-safe palette** (validated blue/green categorical,
  a single blue for magnitude, a diverging blue↔red for correlation) with
  recessive grid/axes, so identity never rests on hue alone.

Run it with:  ``python -m src.analysis.eda``
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure

from src import config
from src.analysis import sql_analytics
from src.database.connection import get_connection
from src.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Palette (validated, colorblind-safe — light chart surface)
# ---------------------------------------------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"   # categorical slot 1 / single-hue magnitude
GREEN = "#008300"  # categorical slot 2
RED = "#e34948"    # diverging warm pole (correlation only)

# Color follows the entity, never its rank — one fixed mapping everywhere.
TYPE_COLORS = {"Movie": BLUE, "TV Show": GREEN}

# Diverging blue↔gray↔red colormap for correlation (-1 … +1).
_CORR_CMAP = LinearSegmentedColormap.from_list(
    "blue_gray_red", [BLUE, "#f0efec", RED]
)


# ---------------------------------------------------------------------------
# Chart chrome helpers
# ---------------------------------------------------------------------------
def _new_fig(width: float = 8.0, height: float = 4.5) -> tuple[Figure, plt.Axes]:
    """Create a styled figure/axes with the project's recessive chrome."""
    fig, ax = plt.subplots(figsize=(width, height), dpi=120)
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax)
    return fig, ax


def _style_axes(ax: plt.Axes) -> None:
    """Apply recessive grid/axes and muted ink to an axes."""
    ax.set_facecolor(SURFACE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(AXIS)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=INK_MUTED, labelsize=9)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)
    ax.title.set_color(INK)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _bar_labels(ax: plt.Axes, bars, values, horizontal: bool = False) -> None:
    """Direct-label each bar with its value (labels stay in muted ink)."""
    for bar, value in zip(bars, values):
        if horizontal:
            ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                    f" {value:,.0f}", va="center", ha="left",
                    color=INK_SECONDARY, fontsize=8)
        else:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{value:,.0f}", va="bottom", ha="center",
                    color=INK_SECONDARY, fontsize=8)


# ---------------------------------------------------------------------------
# Data loading & tabular analyses (each returns a DataFrame)
# ---------------------------------------------------------------------------
def load_titles(conn) -> pd.DataFrame:
    """Load the one-row-per-title entity table for pandas-side EDA."""
    df = pd.read_sql_query("SELECT * FROM titles", conn)
    log.info("Loaded %d titles for EDA", len(df))
    return df


def numeric_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Descriptive stats for the numeric columns (transposed for readability)."""
    cols = [c for c in ("release_year", "year_added", "duration_value") if c in df]
    return df[cols].describe().T


def runtime_outliers(df: pd.DataFrame) -> dict[str, float]:
    """IQR-based outlier bounds and counts for movie runtimes (minutes)."""
    runtimes = df.loc[df["duration_unit"] == "Minutes", "duration_value"].dropna()
    q1, q3 = runtimes.quantile(0.25), runtimes.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = runtimes[(runtimes < lower) | (runtimes > upper)]
    return {
        "n_movies": int(runtimes.shape[0]),
        "q1": float(q1), "median": float(runtimes.median()), "q3": float(q3),
        "iqr": float(iqr), "lower_bound": float(lower), "upper_bound": float(upper),
        "n_outliers": int(outliers.shape[0]),
        "min": float(runtimes.min()), "max": float(runtimes.max()),
    }


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation among numeric fields, on the movie subset.

    Restricting to movies makes ``duration_value`` a single unit (minutes), so
    the runtime correlations are meaningful rather than mixing minutes/seasons.
    """
    movies = df[df["duration_unit"] == "Minutes"].copy()
    cols = {"release_year": "release_year", "year_added": "year_added",
            "duration_value": "runtime_min"}
    sub = movies[list(cols)].rename(columns=cols)
    return sub.corr(numeric_only=True).round(2)


# ---------------------------------------------------------------------------
# Charts (each returns a Figure)
# ---------------------------------------------------------------------------
def plot_type_split(df: pd.DataFrame) -> Figure:
    """Bar chart: Movie vs TV Show counts."""
    counts = df["type"].value_counts()
    fig, ax = _new_fig(6, 4)
    bars = ax.bar(counts.index, counts.values,
                  color=[TYPE_COLORS[t] for t in counts.index], width=0.6)
    _bar_labels(ax, bars, counts.values)
    ax.set_title("Catalog composition — Movies vs TV Shows", fontsize=12, pad=12)
    ax.set_ylabel("Number of titles")
    ax.margins(y=0.12)
    fig.tight_layout()
    return fig


def plot_rating_distribution(df: pd.DataFrame) -> Figure:
    """Bar chart: number of titles per maturity rating (descending)."""
    counts = df["rating"].value_counts()
    fig, ax = _new_fig(9, 4.5)
    bars = ax.bar(counts.index.astype(str), counts.values, color=BLUE, width=0.7)
    _bar_labels(ax, bars, counts.values)
    ax.set_title("Distribution across maturity ratings", fontsize=12, pad=12)
    ax.set_ylabel("Number of titles")
    ax.margins(y=0.12)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    return fig


def plot_release_year_hist(df: pd.DataFrame) -> Figure:
    """Histogram of release years — how old the catalog's content is."""
    years = df["release_year"].dropna()
    fig, ax = _new_fig(9, 4.5)
    ax.hist(years, bins=range(int(years.min()), int(years.max()) + 2),
            color=BLUE, edgecolor=SURFACE, linewidth=0.4)
    ax.set_title("When catalog titles were released", fontsize=12, pad=12)
    ax.set_xlabel("Release year")
    ax.set_ylabel("Number of titles")
    fig.tight_layout()
    return fig


def plot_titles_added_over_time(df: pd.DataFrame) -> Figure:
    """Line chart: titles added per year, split by type."""
    added = df.dropna(subset=["year_added"]).copy()
    added["year_added"] = added["year_added"].astype(int)
    pivot = (added.groupby(["year_added", "type"]).size()
             .unstack(fill_value=0).sort_index())
    fig, ax = _new_fig(9, 4.5)
    for type_name in ("Movie", "TV Show"):
        if type_name in pivot:
            ax.plot(pivot.index, pivot[type_name], marker="o", markersize=4,
                    linewidth=2, color=TYPE_COLORS[type_name], label=type_name)
    ax.set_title("Titles added to Netflix per year", fontsize=12, pad=12)
    ax.set_xlabel("Year added")
    ax.set_ylabel("Titles added")
    ax.legend(frameon=False, labelcolor=INK_SECONDARY, fontsize=9)
    fig.tight_layout()
    return fig


def plot_top_genres(conn, top_n: int = 15) -> Figure:
    """Horizontal bar chart of the most common genres (reuses the M6 query)."""
    genres = sql_analytics.run_query("top_genres", conn).head(top_n)
    return _horizontal_ranking(
        genres["genre_name"], genres["n_titles"],
        "Most common genres", "Genre memberships",
    )


def plot_top_countries(conn, top_n: int = 15) -> Figure:
    """Horizontal bar chart of the top producing countries (reuses the M6 query)."""
    countries = sql_analytics.run_query("top_countries", conn).head(top_n)
    return _horizontal_ranking(
        countries["country_name"], countries["n_titles"],
        "Top producing countries", "Number of titles",
    )


def _horizontal_ranking(labels, values, title: str, xlabel: str) -> Figure:
    """Shared horizontal-bar renderer for the top-N ranking charts."""
    fig, ax = _new_fig(8, 5.5)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    y = range(len(labels))
    bars = ax.barh(list(y), list(values), color=BLUE, height=0.72)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()  # largest on top
    _bar_labels(ax, bars, values, horizontal=True)
    ax.set_title(title, fontsize=12, pad=12)
    ax.set_xlabel(xlabel)
    ax.margins(x=0.10)
    fig.tight_layout()
    return fig


def plot_runtime_distribution(df: pd.DataFrame) -> Figure:
    """Histogram of movie runtimes with IQR outlier bounds marked."""
    stats = runtime_outliers(df)
    runtimes = df.loc[df["duration_unit"] == "Minutes", "duration_value"].dropna()
    fig, ax = _new_fig(9, 4.5)
    ax.hist(runtimes, bins=40, color=BLUE, edgecolor=SURFACE, linewidth=0.4)
    for bound in (stats["lower_bound"], stats["upper_bound"]):
        ax.axvline(bound, color=INK_MUTED, linestyle="--", linewidth=1.2)
    ax.axvline(stats["median"], color=GREEN, linestyle="-", linewidth=1.5)
    ax.set_title(
        f"Movie runtime distribution "
        f"(median {stats['median']:.0f} min · {stats['n_outliers']:,} IQR outliers)",
        fontsize=12, pad=12,
    )
    ax.set_xlabel("Runtime (minutes)")
    ax.set_ylabel("Number of movies")
    # Small legend clarifying the reference lines.
    ax.plot([], [], color=GREEN, linewidth=1.5, label="Median")
    ax.plot([], [], color=INK_MUTED, linestyle="--", linewidth=1.2, label="IQR fence (1.5×)")
    ax.legend(frameon=False, labelcolor=INK_SECONDARY, fontsize=9)
    fig.tight_layout()
    return fig


def plot_correlation_heatmap(df: pd.DataFrame) -> Figure:
    """Diverging heatmap of the numeric-field correlations (movies only)."""
    corr = correlation_matrix(df)
    fig, ax = _new_fig(5.5, 5)
    ax.grid(False)
    im = ax.imshow(corr.values, cmap=_CORR_CMAP, vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.index)))
    ax.set_xticklabels(corr.columns, rotation=30, ha="right")
    ax.set_yticklabels(corr.index)
    for i in range(len(corr.index)):
        for j in range(len(corr.columns)):
            value = corr.values[i, j]
            ax.text(j, i, f"{value:.2f}", ha="center", va="center",
                    color=INK if abs(value) < 0.6 else SURFACE, fontsize=10)
    ax.set_title("Numeric-field correlations (movies)", fontsize=12, pad=12)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Figure orchestration
# ---------------------------------------------------------------------------
# (filename stem, builder). Builders taking a connection get it; the rest get df.
def generate_figures(conn) -> dict[str, Figure]:
    """Build every EDA figure, keyed by its filename stem."""
    df = load_titles(conn)
    figures: dict[str, Figure] = {
        "type_split": plot_type_split(df),
        "rating_distribution": plot_rating_distribution(df),
        "release_year_hist": plot_release_year_hist(df),
        "titles_added_over_time": plot_titles_added_over_time(df),
        "top_genres": plot_top_genres(conn),
        "top_countries": plot_top_countries(conn),
        "runtime_distribution": plot_runtime_distribution(df),
        "correlation_heatmap": plot_correlation_heatmap(df),
    }
    return figures


def save_all_figures(conn, figures_dir: Path = config.FIGURES_DIR) -> list[Path]:
    """Render and save every EDA figure as a PNG; return the saved paths."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for stem, fig in generate_figures(conn).items():
        path = figures_dir / f"{stem}.png"
        fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)
        saved.append(path)
        log.info("Saved figure %s", path.name)
    return saved


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
def _figures_table(df: pd.DataFrame) -> list[str]:
    """Render a small DataFrame (with an index) as Markdown table lines."""
    header = ["| " + " | ".join([df.index.name or ""] + [str(c) for c in df.columns]) + " |"]
    header.append("| " + " | ".join("---" for _ in range(len(df.columns) + 1)) + " |")
    rows = []
    for idx, row in df.iterrows():
        cells = [f"{v:,.2f}" if isinstance(v, float) else str(v) for v in row]
        rows.append("| " + " | ".join([str(idx)] + cells) + " |")
    return header + rows


def build_eda_report(df: pd.DataFrame, corr: pd.DataFrame,
                     outliers: dict[str, float]) -> str:
    """Assemble the EDA findings report (embeds the saved figures)."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(df)
    n_movies = int((df["type"] == "Movie").sum())
    n_shows = total - n_movies
    peak_year = (df.dropna(subset=["year_added"]).astype({"year_added": int})
                 ["year_added"].value_counts().idxmax())
    summary = numeric_summary(df)

    def fig(stem: str, alt: str) -> str:
        return f"![{alt}](figures/{stem}.png)"

    sections = [
        "# 🔍 Exploratory Data Analysis — Netflix Catalog",
        "",
        f"- **Generated:** {generated}",
        "- **Source:** `data/database/netflix.db` (normalized SQLite DB, Milestone 5)",
        f"- **Grain:** one row per title — {total:,} titles "
        f"({n_movies:,} Movies, {n_shows:,} TV Shows)",
        "",
        "> Auto-generated by `src/analysis/eda.py`. Distributions and outliers are "
        "computed in pandas on the `titles` table; the ranking charts reuse the "
        "Milestone 6 SQL analytics layer. See `notebooks/eda.ipynb` for the "
        "narrative walk-through.",
        "",
        "## 1. Catalog Composition",
        "",
        fig("type_split", "Movies vs TV Shows"),
        "",
        f"- The catalog is **{100 * n_movies / total:.1f}% Movies / "
        f"{100 * n_shows / total:.1f}% TV Shows** — movie-heavy, but TV has grown "
        "fastest in recent years (see §3).",
        "",
        fig("rating_distribution", "Maturity-rating distribution"),
        "",
        "- Ratings are dominated by mature audiences: **TV-MA** and **TV-14** "
        "together account for roughly 6 in 10 titles.",
        "",
        "## 2. Content Age",
        "",
        fig("release_year_hist", "Release-year distribution"),
        "",
        "- Release years are **heavily left-skewed**: the vast majority of titles "
        "are from the 2010s onward, with a long thin tail of older classics.",
        "",
        "## 3. Growth Over Time",
        "",
        fig("titles_added_over_time", "Titles added per year by type"),
        "",
        f"- Additions accelerated sharply after 2015 and **peaked in {peak_year}**. "
        "TV Show additions climb faster than Movies late in the series, narrowing "
        "the gap.",
        "",
        "## 4. Movie Runtime & Outliers",
        "",
        fig("runtime_distribution", "Movie runtime distribution with IQR fences"),
        "",
        f"- Movie runtimes center on a **median of {outliers['median']:.0f} minutes** "
        f"(IQR {outliers['q1']:.0f}–{outliers['q3']:.0f}). Using the 1.5×IQR rule, "
        f"**{outliers['n_outliers']:,} of {outliers['n_movies']:,} movies** fall "
        f"outside the fence "
        f"[{outliers['lower_bound']:.0f}, {outliers['upper_bound']:.0f}] min — from "
        f"{outliers['min']:.0f}-min shorts to a {outliers['max']:.0f}-min extreme.",
        "",
        "## 5. Numeric Relationships",
        "",
        fig("correlation_heatmap", "Correlation heatmap (movies)"),
        "",
        "**Correlation matrix (movies only):**",
        "",
        *_figures_table(corr),
        "",
        "- The catalog is **overwhelmingly categorical** — only three numeric "
        "fields exist. Correlations are weak: newer movies trend very slightly "
        "shorter, but there is no strong linear relationship to exploit. This is "
        "itself a finding — insight here comes from the categorical dimensions "
        "(genre, country, type), not numeric regression.",
        "",
        "## 6. Numeric Summary",
        "",
        *_figures_table(summary),
        "",
    ]
    return "\n".join(sections)


def save_eda_report(df: pd.DataFrame, corr: pd.DataFrame,
                    outliers: dict[str, float],
                    path: Path = config.EDA_REPORT) -> Path:
    """Build and write the Markdown EDA report."""
    config.ensure_directories()
    path.write_text(build_eda_report(df, corr, outliers), encoding="utf-8")
    log.info("EDA report written to %s", path)
    return path


def main() -> None:
    """Ensure the DB exists, render all figures, and write the EDA report."""
    # Headless, file-only rendering for the script path (never opens a window).
    # Set here rather than at import so notebooks keep their inline backend.
    matplotlib.use("Agg")
    sql_analytics.ensure_database()
    with get_connection() as conn:
        df = load_titles(conn)
        saved = save_all_figures(conn)
        corr = correlation_matrix(df)
        outliers = runtime_outliers(df)

    out = save_eda_report(df, corr, outliers)

    print("\n=== EDA SUMMARY ===")
    print(f"  Titles analyzed : {len(df):,}")
    print(f"  Figures written : {len(saved)}  -> {config.FIGURES_DIR}")
    print(f"  Movie runtime   : median {outliers['median']:.0f} min, "
          f"{outliers['n_outliers']:,} IQR outliers")
    print(f"\n[OK] EDA report saved to: {out}")


if __name__ == "__main__":
    main()
