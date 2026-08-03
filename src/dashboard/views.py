"""Dashboard pages (Milestones 13–14).

One render function per page. Each is thin: it pulls cached data/models from
:mod:`src.dashboard.data`, builds figures with the Milestone-9 chart library, and
lays them out. Milestone 14 adds the advanced features — genre/country filters,
filter-aware breakdowns, CSV export, a title drill-down, and cross-page
"recommend similar" navigation via ``st.session_state`` + ``st.switch_page``.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard import data
from src.visualization import charts, theme

# Headline KPIs to show as stat tiles on the overview (two rows of four).
TILE_KEYS = [
    "total_titles", "movies", "tv_shows", "additions_cagr",
    "new_release_share", "international_share", "effective_genres",
    "median_movie_runtime",
]


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------
def _download_button(df: pd.DataFrame, filename: str, label: str = "⬇️ Download CSV") -> None:
    """A CSV download button for any result table."""
    st.download_button(
        label, df.to_csv(index=False).encode("utf-8"),
        file_name=filename, mime="text/csv",
    )


def _explode_counts(series: pd.Series, top: int = 15,
                    drop_unknown: bool = False) -> pd.DataFrame:
    """Count individual values in a comma-joined multi-value column."""
    exploded = series.fillna("").str.split(",").explode().str.strip()
    exploded = exploded[exploded != ""]
    if drop_unknown:
        exploded = exploded[exploded != "Unknown"]
    counts = exploded.value_counts().head(top)
    return counts.rename_axis("name").reset_index(name="n_titles")


def _has_any(cell: str, selected: set[str]) -> bool:
    """True if a comma-joined cell shares any value with the selected set."""
    return bool(selected & {x.strip() for x in str(cell).split(",")})


# ---------------------------------------------------------------------------
# Page 1 — Overview
# ---------------------------------------------------------------------------
def overview() -> None:
    st.title("🎬 Netflix Content Analytics")
    st.caption(
        "A catalog analytics platform over ~8,800 Netflix titles — composition, "
        "growth, diversity, and reach. This is a catalog snapshot (through Sep "
        "2021); it measures *what the library contains*, not popularity."
    )

    kpi = {k.key: k for k in data.get_kpis()}
    for row_keys in (TILE_KEYS[:4], TILE_KEYS[4:]):
        for col, key in zip(st.columns(4), row_keys):
            k = kpi[key]
            col.metric(k.label, k.formatted(), help=k.description)

    st.subheader("🔑 Key Insights")
    for insight in data.get_insights()[:5]:
        st.markdown(f"- {insight.text}")

    st.subheader("Catalog at a glance")
    left, right = st.columns(2)
    left.plotly_chart(
        charts.donut(data.query("content_type_split"), names="type",
                     values="n_titles", title="Movies vs TV Shows",
                     color="type", color_discrete_map=theme.TYPE_COLORS),
        use_container_width=True,
    )
    right.plotly_chart(
        charts.line(data.added_by_year_type(), x="year_added", y="titles_added",
                    color="type", title="Titles added per year",
                    color_discrete_map=theme.TYPE_COLORS),
        use_container_width=True,
    )
    st.plotly_chart(
        charts.treemap(data.genre_counts(), path=["genre_name"], values="n_titles",
                       title="Genre share of the catalog"),
        use_container_width=True,
    )
    st.plotly_chart(
        charts.choropleth(data.country_counts(), locations="country_name",
                          values="n_titles", title="Titles produced per country"),
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Page 2 — Explore (filterable, with genre/country + browse + export)
# ---------------------------------------------------------------------------
def explore() -> None:
    st.title("🔎 Explore the catalog")
    titles = data.load_enriched_titles()

    st.sidebar.header("Filters")
    type_choice = st.sidebar.radio("Type", ["All", "Movie", "TV Show"], horizontal=True)
    y_min, y_max = int(titles["release_year"].min()), int(titles["release_year"].max())
    year_range = st.sidebar.slider("Release year", y_min, y_max, (y_min, y_max))
    chosen_ratings = st.sidebar.multiselect(
        "Rating", sorted(titles["rating"].dropna().unique()),
        help="Leave empty to include all ratings.")
    chosen_genres = st.sidebar.multiselect(
        "Genre", sorted(data.genre_counts()["genre_name"]))
    chosen_countries = st.sidebar.multiselect(
        "Country", data.country_counts().sort_values(
            "n_titles", ascending=False)["country_name"].tolist())

    view = titles[titles["release_year"].between(*year_range)]
    if type_choice != "All":
        view = view[view["type"] == type_choice]
    if chosen_ratings:
        view = view[view["rating"].isin(chosen_ratings)]
    if chosen_genres:
        sel = set(chosen_genres)
        view = view[view["genres"].apply(lambda c: _has_any(c, sel))]
    if chosen_countries:
        sel = set(chosen_countries)
        view = view[view["countries"].apply(lambda c: _has_any(c, sel))]

    st.caption(f"**{len(view):,}** of {len(titles):,} titles match the filters.")
    if view.empty:
        st.warning("No titles match these filters — widen them to see charts.")
        return

    type_counts = (view["type"].value_counts()
                   .rename_axis("type").reset_index(name="n_titles"))
    rating_counts = (view["rating"].value_counts()
                     .rename_axis("rating").reset_index(name="n_titles"))
    added = (view.dropna(subset=["year_added"]).astype({"year_added": int})
             .groupby(["year_added", "type"]).size().reset_index(name="titles_added"))

    left, right = st.columns(2)
    left.plotly_chart(
        charts.donut(type_counts, names="type", values="n_titles",
                     title="Type split", color="type",
                     color_discrete_map=theme.TYPE_COLORS),
        use_container_width=True)
    right.plotly_chart(
        charts.bar(rating_counts, x="rating", y="n_titles",
                   title="Ratings distribution"),
        use_container_width=True)

    gcol, ccol = st.columns(2)
    gcol.plotly_chart(
        charts.bar(_explode_counts(view["genres"]), x="n_titles", y="name",
                   horizontal=True, title="Top genres (filtered)"),
        use_container_width=True)
    ccol.plotly_chart(
        charts.bar(_explode_counts(view["countries"], drop_unknown=True),
                   x="n_titles", y="name", horizontal=True,
                   title="Top countries (filtered)"),
        use_container_width=True)

    if not added.empty:
        st.plotly_chart(
            charts.line(added, x="year_added", y="titles_added", color="type",
                        title="Titles added per year",
                        color_discrete_map=theme.TYPE_COLORS),
            use_container_width=True)

    st.subheader("Browse titles")
    browse = (view[["title", "type", "release_year", "rating", "genres", "countries"]]
              .sort_values("title"))
    st.dataframe(
        browse, use_container_width=True, hide_index=True, height=320,
        column_config={
            "title": "Title", "type": "Type",
            "release_year": st.column_config.NumberColumn("Year", format="%d"),
            "rating": "Rating", "genres": "Genres", "countries": "Country",
        })
    _download_button(browse, "netflix_filtered.csv")

    # Cross-page link: send a chosen title to the recommender.
    st.divider()
    picks = ["—"] + sorted(view["title"].unique().tolist())
    pick_col, btn_col = st.columns([3, 1])
    pick = pick_col.selectbox("Get recommendations for a title in these results",
                              picks, key="explore_pick")
    btn_col.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if btn_col.button("🎯 Recommend similar", use_container_width=True,
                      disabled=(pick == "—")):
        st.session_state["rec_seed_select"] = pick
        st.switch_page(st.session_state["_pages"]["recommend"])


# ---------------------------------------------------------------------------
# Page 3 — Recommend (with drill-down + export)
# ---------------------------------------------------------------------------
def recommend() -> None:
    st.title("🎯 Find similar titles")
    st.caption(
        "Content-based recommendations: pick a title and get the most similar ones "
        "by TF-IDF cosine similarity over description, genres, cast, and directors."
    )
    recommender = data.get_recommender()
    options = data.title_options()
    st.session_state.setdefault(
        "rec_seed_select", "Breaking Bad" if "Breaking Bad" in options else options[0])

    seed = st.selectbox("Pick a title you like", options, key="rec_seed_select")
    n = st.slider("How many recommendations", 5, 20, 10)

    if not seed:
        return
    recs, seed_row = recommender.recommend(seed, n=n)
    st.markdown(f"**{seed_row['title']}** &nbsp;·&nbsp; {seed_row['type']} "
                f"&nbsp;·&nbsp; {int(seed_row['release_year'])}")
    st.caption(f"Genres: {seed_row['genres']}")

    with st.expander(f"About “{seed_row['title']}”"):
        st.write(seed_row["description"] or "No description available.")
        st.markdown(f"**Director(s):** {seed_row['directors'] or '—'}")
        st.markdown(f"**Cast:** {seed_row['cast'] or '—'}")
        st.markdown(f"**Country:** {seed_row['countries'] or '—'}")

    st.dataframe(
        recs, use_container_width=True, hide_index=True,
        column_config={
            "title": "Title", "type": "Type",
            "release_year": st.column_config.NumberColumn("Year", format="%d"),
            "similarity": st.column_config.ProgressColumn(
                "Similarity", min_value=0.0, max_value=1.0, format="%.3f"),
            "shared_genres": "Shared genres",
        })
    _download_button(recs, "recommendations.csv")


# ---------------------------------------------------------------------------
# Page 4 — Search (with export)
# ---------------------------------------------------------------------------
def search() -> None:
    st.title("🔍 Natural-language search")
    st.caption(
        "Free-text search over the catalog — ranked by relevance (TF-IDF cosine "
        "over each title's text and metadata)."
    )
    engine = data.get_search_engine()

    query = st.text_input("Describe what you want to watch",
                          placeholder="e.g. dark psychological thriller")
    left, right = st.columns(2)
    n = left.slider("Results", 5, 20, 10)
    type_choice = right.radio("Type", ["All", "Movie", "TV Show"], horizontal=True)

    if not query:
        st.caption("Type a description above to search the catalog.")
        return

    type_filter = None if type_choice == "All" else type_choice
    results = engine.search(query, n=n, type_filter=type_filter)
    if results.empty:
        st.info("No matching titles — try different words.")
        return
    st.dataframe(
        results, use_container_width=True, hide_index=True,
        column_config={
            "title": "Title", "type": "Type",
            "release_year": st.column_config.NumberColumn("Year", format="%d"),
            "genres": "Genres",
            "score": st.column_config.ProgressColumn(
                "Relevance", min_value=0.0, max_value=1.0, format="%.3f"),
        })
    _download_button(results, "search_results.csv")
