"""House visualization theme (Milestone 9).

Defines a single Plotly **template** — ``netflix_analytics`` — that carries the
project's validated, colorblind-safe palette and recessive chrome, and registers
it as the default. Importing this module (which ``charts.py`` does) means every
figure the library builds inherits one consistent look, so the dashboard reads as
one system rather than a pile of differently-styled charts.

The palette is the same validated instance used for the M7 static charts, now
expressed as a Plotly colorway + sequential scale, so the interactive and static
visuals match.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------------------
# Palette (validated, colorblind-safe — light chart surface)
# ---------------------------------------------------------------------------
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

# Categorical colorway — the validated 8-hue order (max-min adjacent CVD ΔE).
COLORWAY = [
    "#2a78d6",  # 1 blue
    "#008300",  # 2 green
    "#e87ba4",  # 3 magenta
    "#eda100",  # 4 yellow
    "#1baf7a",  # 5 aqua
    "#eb6834",  # 6 orange
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]

# One fixed mapping for the ever-present content-type split (color follows the
# entity, never its position), so Movies/TV read the same on every chart.
TYPE_COLORS = {"Movie": "#2a78d6", "TV Show": "#008300"}

# Single-hue blue ramp for continuous magnitude (choropleth, treemap).
SEQUENTIAL_BLUE = [
    [0.0, "#cde2fb"], [0.25, "#86b6ef"], [0.5, "#3987e5"],
    [0.75, "#1c5cab"], [1.0, "#0d366b"],
]

FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

TEMPLATE_NAME = "netflix_analytics"


def _build_template() -> go.layout.Template:
    """Construct the house Plotly template from the palette above."""
    axis = dict(
        showgrid=True, gridcolor=GRID, gridwidth=1,
        linecolor=AXIS, zerolinecolor=GRID,
        tickfont=dict(color=INK_MUTED, size=12),
        title=dict(font=dict(color=INK_SECONDARY, size=13)),
        automargin=True,
    )
    template = go.layout.Template()
    template.layout = go.Layout(
        colorway=COLORWAY,
        colorscale=dict(sequential=SEQUENTIAL_BLUE),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT_FAMILY, color=INK, size=13),
        title=dict(font=dict(color=INK, size=17), x=0.01, xanchor="left"),
        xaxis=axis,
        yaxis={**axis, "gridcolor": GRID},
        legend=dict(
            font=dict(color=INK_SECONDARY, size=12),
            bgcolor="rgba(0,0,0,0)", title=dict(font=dict(color=INK_SECONDARY)),
        ),
        margin=dict(t=64, l=64, r=28, b=52),
        hoverlabel=dict(
            bgcolor=SURFACE, bordercolor=AXIS,
            font=dict(family=FONT_FAMILY, color=INK, size=12),
        ),
        geo=dict(
            bgcolor=SURFACE, lakecolor=SURFACE, landcolor="#eef0f2",
            showland=True, showcountries=True, countrycolor=GRID,
            coastlinecolor=AXIS,
        ),
    )
    return template


def register_theme(*, set_default: bool = True) -> str:
    """Register the house template with Plotly (and set it as default)."""
    pio.templates[TEMPLATE_NAME] = _build_template()
    if set_default:
        pio.templates.default = TEMPLATE_NAME
    return TEMPLATE_NAME


# Register on import so any module using the library inherits the house style.
register_theme()
