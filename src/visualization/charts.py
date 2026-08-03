"""Reusable Plotly chart library (Milestone 9).

Generic, dashboard-ready chart *builders* — each takes a tidy DataFrame and
returns a themed :class:`plotly.graph_objects.Figure`. They are deliberately
generic (you pass the columns), so the same ``bar``/``line``/``choropleth`` power
many dashboard panels rather than being welded to one query. Every figure inherits
the house template from :mod:`src.visualization.theme` on import.

The interactive counterpart to Milestone 7's static matplotlib EDA: same palette,
now hoverable, zoomable, and ready to drop into the Streamlit dashboard (M13).

``main()`` wires the builders to real data (reusing the M6 SQL layer and the M8
KPI engine) and writes a self-contained HTML **gallery** to
``reports/visualization_gallery.html``.

Run it with:  ``python -m src.visualization.charts``
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from src import config
from src.analysis import kpis, sql_analytics
from src.database.connection import get_connection
from src.logger import get_logger
from src.visualization import theme

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Generic chart primitives (each returns a themed go.Figure)
# ---------------------------------------------------------------------------
def bar(df: pd.DataFrame, x: str, y: str, *, title: str = "",
        horizontal: bool = False, text: bool = True, **px_kwargs) -> go.Figure:
    """Bar chart. Set ``horizontal=True`` for a ranked top-N (largest on top)."""
    orientation = "h" if horizontal else "v"
    text_col = (x if horizontal else y) if text else None
    fig = px.bar(df, x=x, y=y, orientation=orientation, title=title,
                 text=text_col, **px_kwargs)
    if text:
        fig.update_traces(texttemplate="%{text:,}", textposition="outside",
                          cliponaxis=False)
    if horizontal:
        fig.update_yaxes(categoryorder="total ascending")  # largest at the top
    fig.update_layout(showlegend="color" in px_kwargs)
    return fig


def line(df: pd.DataFrame, x: str, y: str, *, title: str = "",
         color: str | None = None, **px_kwargs) -> go.Figure:
    """Line chart for change-over-time; ``color`` splits into series."""
    fig = px.line(df, x=x, y=y, color=color, markers=True, title=title,
                  **px_kwargs)
    fig.update_traces(line=dict(width=2.5), marker=dict(size=6))
    return fig


def donut(df: pd.DataFrame, names: str, values: str, *, title: str = "",
          **px_kwargs) -> go.Figure:
    """Donut (pie with a hole) for a small part-to-whole split."""
    fig = px.pie(df, names=names, values=values, hole=0.55, title=title,
                 **px_kwargs)
    fig.update_traces(textposition="outside",
                      texttemplate="%{label}<br>%{percent}",
                      marker=dict(line=dict(color=theme.SURFACE, width=2)))
    return fig


def treemap(df: pd.DataFrame, path: list[str], values: str, *,
            title: str = "", **px_kwargs) -> go.Figure:
    """Treemap for hierarchical / many-category magnitude."""
    fig = px.treemap(df, path=path, values=values, title=title,
                     color=values, color_continuous_scale=theme.SEQUENTIAL_BLUE,
                     **px_kwargs)
    fig.update_traces(marker=dict(line=dict(color=theme.SURFACE, width=1.5)))
    return fig


def choropleth(df: pd.DataFrame, locations: str, values: str, *,
               title: str = "", **px_kwargs) -> go.Figure:
    """World choropleth keyed on full country names."""
    fig = px.choropleth(
        df, locations=locations, locationmode="country names", color=values,
        color_continuous_scale=theme.SEQUENTIAL_BLUE, title=title, **px_kwargs,
    )
    # Pin the lon/lat window to the whole world so the map fills its container
    # (a bare natural-earth projection otherwise renders as a tiny thumbnail).
    fig.update_geos(
        projection_type="natural earth", showframe=False,
        lonaxis_range=[-170, 190], lataxis_range=[-58, 85],
    )
    fig.update_layout(margin=dict(l=8, r=8, t=60, b=8))
    return fig


def histogram(df: pd.DataFrame, x: str, *, title: str = "",
              nbins: int | None = None, **px_kwargs) -> go.Figure:
    """Histogram for a single numeric distribution."""
    fig = px.histogram(df, x=x, nbins=nbins, title=title, **px_kwargs)
    fig.update_traces(marker=dict(line=dict(color=theme.SURFACE, width=0.5)))
    fig.update_layout(bargap=0.02)
    return fig


def kpi_row(indicators: list[dict]) -> go.Figure:
    """A row of KPI stat tiles (Plotly Indicators) from the M8 metrics.

    Each item: ``{"value": float, "title": str, "suffix": str, "fmt": str}``.
    """
    fig = make_subplots(
        rows=1, cols=len(indicators),
        specs=[[{"type": "indicator"} for _ in indicators]],
    )
    for i, ind in enumerate(indicators):
        fig.add_trace(
            go.Indicator(
                mode="number",
                value=ind["value"],
                number=dict(suffix=ind.get("suffix", ""),
                            valueformat=ind.get("fmt", ","),
                            font=dict(size=40, color=theme.COLORWAY[0])),
                title=dict(text=ind["title"],
                           font=dict(size=14, color=theme.INK_SECONDARY)),
            ),
            row=1, col=i + 1,
        )
    fig.update_layout(margin=dict(t=30, l=20, r=20, b=10), height=170)
    return fig


# ---------------------------------------------------------------------------
# Gallery: wire the builders to real data
# ---------------------------------------------------------------------------
def _added_by_year_type(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT year_added, type, COUNT(*) AS titles_added "
        "FROM titles WHERE year_added IS NOT NULL "
        "GROUP BY year_added, type ORDER BY year_added",
        conn,
    )


def _all_genre_counts(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT g.genre_name, COUNT(*) AS n_titles "
        "FROM title_genres tg JOIN genres g ON g.genre_id = tg.genre_id "
        "GROUP BY g.genre_name ORDER BY n_titles DESC",
        conn,
    )


def _country_counts(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT c.country_name, COUNT(*) AS n_titles "
        "FROM title_countries tc JOIN countries c ON c.country_id = tc.country_id "
        "WHERE c.country_name <> 'Unknown' "
        "GROUP BY c.country_name",
        conn,
    )


def build_gallery_figures(conn) -> dict[str, go.Figure]:
    """Build the showcase set of figures from live data."""
    type_split = sql_analytics.run_query("content_type_split", conn)
    top_genres = sql_analytics.run_query("top_genres", conn)
    top_countries = sql_analytics.run_query("top_countries", conn)
    ratings = sql_analytics.run_query("rating_distribution", conn)
    by_decade = sql_analytics.run_query("content_by_decade", conn)
    added = _added_by_year_type(conn)
    genres_all = _all_genre_counts(conn)
    countries_all = _country_counts(conn)

    # Long-form movies/TV per decade for a grouped bar.
    decade_long = by_decade.melt(
        id_vars="decade", value_vars=["movies", "tv_shows"],
        var_name="type", value_name="n_titles",
    ).replace({"movies": "Movie", "tv_shows": "TV Show"})

    # A few headline KPIs as stat tiles.
    kpi_list = {k.key: k for k in kpis.compute_kpis(conn)}
    tiles = [
        dict(value=kpi_list["total_titles"].value, title="Total titles", fmt=","),
        dict(value=kpi_list["movies"].value, title="Movies", fmt=","),
        dict(value=kpi_list["additions_cagr"].value, title="Additions CAGR",
             suffix="%", fmt=".1f"),
        dict(value=kpi_list["international_share"].value, title="International share",
             suffix="%", fmt=".1f"),
    ]

    return {
        "KPI scorecard (stat tiles)": kpi_row(tiles),
        "Movies vs TV Shows": donut(
            type_split, names="type", values="n_titles",
            title="Catalog composition — Movies vs TV Shows",
            color="type", color_discrete_map=theme.TYPE_COLORS),
        "Titles added per year": line(
            added, x="year_added", y="titles_added", color="type",
            title="Titles added to Netflix per year",
            color_discrete_map=theme.TYPE_COLORS),
        "Movies vs TV by decade": bar(
            decade_long, x="decade", y="n_titles", title="Releases by decade",
            text=False, color="type", barmode="group",
            color_discrete_map=theme.TYPE_COLORS),
        "Top genres": bar(
            top_genres, x="n_titles", y="genre_name", horizontal=True,
            title="Most common genres"),
        "Top countries": bar(
            top_countries, x="n_titles", y="country_name", horizontal=True,
            title="Top producing countries"),
        "Maturity ratings": bar(
            ratings, x="rating", y="n_titles", title="Distribution across ratings"),
        "Genre treemap": treemap(
            genres_all, path=["genre_name"], values="n_titles",
            title="Genre share of the catalog"),
        "Titles by country (world map)": choropleth(
            countries_all, locations="country_name", values="n_titles",
            title="Titles produced per country"),
    }


# ---------------------------------------------------------------------------
# HTML gallery assembly
# ---------------------------------------------------------------------------
_PAGE_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; background: #f9f9f7; color: #0b0b0b;
       font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
header { padding: 32px 40px 8px; }
header h1 { margin: 0 0 6px; font-size: 24px; }
header p { margin: 0; color: #52514e; max-width: 70ch; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
        gap: 20px; padding: 24px 40px 48px; }
.card { background: #fcfcfb; border: 1px solid rgba(11,11,11,0.10);
        border-radius: 12px; padding: 8px; overflow: hidden; }
.card.wide { grid-column: 1 / -1; }
"""


def build_gallery_html(figures: dict[str, go.Figure]) -> str:
    """Assemble a self-contained HTML gallery page from the figures."""
    cards = []
    for i, (name, fig) in enumerate(figures.items()):
        include = "cdn" if i == 0 else False  # load plotly.js once, via CDN
        div = pio.to_html(fig, include_plotlyjs=include, full_html=False,
                          default_width="100%", default_height="440px",
                          config={"displayModeBar": False, "responsive": True})
        wide = " wide" if i == 0 else ""  # KPI tile row spans full width
        cards.append(f'<section class="card{wide}">{div}</section>')

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Netflix Analytics — Visualization Gallery</title>"
        f"<style>{_PAGE_CSS}</style></head><body>"
        "<header><h1>📊 Visualization Gallery</h1>"
        "<p>Interactive Plotly charts from the reusable "
        "<code>src/visualization</code> library — the building blocks the "
        "Streamlit dashboard is assembled from. Hover, zoom, and pan; every chart "
        "shares one colorblind-safe theme.</p></header>"
        f"<div class='grid'>{''.join(cards)}</div>"
        "</body></html>"
    )


def save_gallery(figures: dict[str, go.Figure],
                 path: Path = config.VIZ_GALLERY) -> Path:
    """Build and write the HTML gallery."""
    config.ensure_directories()
    path.write_text(build_gallery_html(figures), encoding="utf-8")
    log.info("Visualization gallery written to %s", path)
    return path


def main() -> None:
    """Ensure the DB exists, build every figure, and write the HTML gallery."""
    sql_analytics.ensure_database()
    with get_connection() as conn:
        figures = build_gallery_figures(conn)

    out = save_gallery(figures)

    print("\n=== VISUALIZATION GALLERY ===")
    for name, fig in figures.items():
        n_traces = len(fig.data)
        print(f"  {name:<32} {n_traces} trace(s)")
    print(f"\n[OK] Gallery written to: {out}")


if __name__ == "__main__":
    main()
