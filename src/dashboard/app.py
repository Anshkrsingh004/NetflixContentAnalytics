"""Streamlit dashboard entry point (Milestone 13).

The user-facing product that ties the whole platform together: KPI stat tiles
(M8), the Plotly chart library (M9), the recommender (M10), natural-language
search (M11), and automated insights (M12), over the normalized database (M5).

Run it with:  ``streamlit run src/dashboard/app.py``

Architecture: this file only configures the page and wires up navigation.
``data.py`` owns cached data/model access; ``views.py`` owns the page rendering.
"""

from __future__ import annotations

import pathlib
import sys

# Make ``src`` importable when Streamlit runs this file directly (its own folder,
# not the repo root, is what lands on sys.path otherwise).
_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st  # noqa: E402  (must follow the sys.path bootstrap)

st.set_page_config(
    page_title="Netflix Content Analytics",
    page_icon="🎬",
    layout="wide",
)

from src.dashboard import views  # noqa: E402  (import after set_page_config)

navigation = st.navigation([
    st.Page(views.overview, title="Overview", icon="📊", default=True),
    st.Page(views.explore, title="Explore", icon="🔎"),
    st.Page(views.recommend, title="Recommend", icon="🎯"),
    st.Page(views.search, title="Search", icon="🔍"),
])
navigation.run()
