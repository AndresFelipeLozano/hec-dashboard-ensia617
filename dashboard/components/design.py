"""Central visual tokens and Plotly theme for the HEC interface."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st


TOKENS: dict[str, str] = {
    "page": "#F4F6F8",
    "surface": "#FFFFFF",
    "teal_900": "#0F3D3E",
    "teal_700": "#146356",
    "teal_500": "#1A8F8C",
    "teal_100": "#DCEDEC",
    "text": "#1C2B2C",
    "muted": "#5F7274",
    "line": "#D8E0E1",
    "soft": "#EEF3F3",
}

PALETTE = [
    TOKENS["teal_500"],
    "#65758B",
    "#2F80ED",
    "#8A6D3B",
    "#7A5268",
]
SPECIALTY_PALETTE = [
    "#1A8F8C",
    "#4C78A8",
    "#F28E2B",
    "#7A5268",
    "#59A14F",
    "#B7791F",
    "#8F63B8",
    "#2A7F9E",
    "#B45F4D",
    "#6F7D3C",
    "#AF7AA1",
    "#486581",
    "#D17C8F",
    "#3A8F7B",
    "#8A6D3B",
]
CURRENT_COLOR = TOKENS["teal_500"]
COMPARISON_COLOR = "#98A2A3"
WARNING_COLOR = "#B7791F"


def render_design_system() -> None:
    """Inject static, responsive presentation styles shared by every page."""

    st.markdown(
        """
        <style>
        :root {
            --hec-page: #F4F6F8;
            --hec-surface: #FFFFFF;
            --hec-teal-900: #0F3D3E;
            --hec-teal-700: #146356;
            --hec-teal-500: #1A8F8C;
            --hec-teal-100: #DCEDEC;
            --hec-text: #1C2B2C;
            --hec-muted: #5F7274;
            --hec-line: #D8E0E1;
            --hec-soft: #EEF3F3;
            --hec-radius: 10px;
            --hec-space: 16px;
        }
        .stApp {
            background: var(--hec-page);
            color: var(--hec-text);
        }
        [data-testid="stMainBlockContainer"] {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }
        [data-testid="stSidebar"] {
            background: #F8FAFA;
            border-right: 1px solid var(--hec-line);
        }
        [data-testid="stHeader"] {
            background: rgba(244, 246, 248, 0.92);
        }
        .hec-app-banner {
            margin: 0 0 1.15rem;
            padding: 1rem 1.2rem 1.05rem;
            border-radius: var(--hec-radius);
            background: linear-gradient(125deg, var(--hec-teal-900), var(--hec-teal-700));
            box-shadow: 0 6px 18px rgba(15, 61, 62, 0.14);
            color: #FFFFFF;
        }
        .hec-app-kicker {
            margin: 0 0 0.2rem;
            color: #BFE1DF;
            font-size: 0.72rem;
            font-weight: 750;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }
        .hec-app-title {
            margin: 0;
            color: #FFFFFF;
            font-size: clamp(1.45rem, 3vw, 2rem);
            font-weight: 750;
            line-height: 1.15;
        }
        .hec-app-subtitle {
            max-width: 88ch;
            margin: 0.35rem 0 0;
            color: #DCEDEC;
            font-size: 0.82rem;
            line-height: 1.45;
        }
        h1, h2, h3, h4 {
            color: var(--hec-text);
            letter-spacing: -0.015em;
        }
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 0.35rem;
            overflow-x: auto;
        }
        [data-testid="stTabs"] button[role="tab"] {
            border-radius: 999px;
            padding-left: 0.9rem;
            padding-right: 0.9rem;
            white-space: nowrap;
        }
        [data-testid="stTabs"] button[aria-selected="true"] {
            background: var(--hec-teal-100);
            color: var(--hec-teal-900);
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--hec-line);
            border-radius: var(--hec-radius);
            background: var(--hec-surface);
            box-shadow: 0 4px 14px rgba(15, 61, 62, 0.045);
        }
        .hec-metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(100%, 175px), 1fr));
            gap: var(--hec-space);
            margin: 0.75rem 0 1rem;
        }
        .hec-metric-card {
            min-width: 0;
            min-height: 132px;
            padding: 1rem 1rem 0.9rem 1.15rem;
            border: 1px solid var(--hec-line);
            border-left: 4px solid var(--hec-teal-500);
            border-radius: var(--hec-radius);
            background: var(--hec-surface);
            box-shadow: 0 4px 14px rgba(15, 61, 62, 0.06);
        }
        .hec-metric-label {
            min-height: 2.3em;
            color: var(--hec-muted);
            font-size: 0.82rem;
            font-weight: 650;
            line-height: 1.25;
        }
        .hec-metric-value {
            margin-top: 0.25rem;
            color: var(--hec-text);
            font-size: clamp(1.55rem, 3vw, 2.05rem);
            font-weight: 750;
            line-height: 1.12;
        }
        .hec-metric-subtitle {
            margin-top: 0.45rem;
            color: var(--hec-muted);
            font-size: 0.74rem;
            line-height: 1.35;
        }
        .hec-badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 0.35rem 0 0.9rem;
        }
        .hec-badge {
            display: inline-flex;
            align-items: center;
            max-width: 100%;
            padding: 0.32rem 0.62rem;
            border: 1px solid var(--hec-line);
            border-radius: 999px;
            background: var(--hec-surface);
            color: var(--hec-muted);
            font-size: 0.75rem;
            font-weight: 600;
            line-height: 1.3;
            overflow-wrap: anywhere;
        }
        .hec-badge--source {
            border-color: #B8D7D5;
            background: #F1F8F7;
            color: var(--hec-teal-900);
        }
        .hec-section-intro {
            max-width: 76ch;
            color: var(--hec-muted);
            font-size: 0.9rem;
            line-height: 1.5;
        }
        @media (max-width: 640px) {
            [data-testid="stMainBlockContainer"] {
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 3.5rem;
            }
            .hec-metric-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.7rem;
            }
            .hec-app-banner {
                margin-bottom: 0.85rem;
                padding: 0.85rem 0.9rem;
            }
            .hec-metric-card {
                min-height: 118px;
                padding: 0.82rem;
                border-left-width: 3px;
            }
            .hec-metric-label {
                min-height: 0;
                font-size: 0.76rem;
            }
            .hec-metric-value {
                font-size: 1.45rem;
            }
        }
        @media (max-width: 360px) {
            .hec-metric-grid {
                grid-template-columns: minmax(0, 1fr);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_plotly_theme(
    figure: go.Figure,
    *,
    height: int | None = None,
    margin: dict[str, int] | None = None,
) -> go.Figure:
    """Apply the shared restrained chart theme without changing chart semantics."""

    layout: dict[str, Any] = {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {
            "family": "Arial, sans-serif",
            "size": 13,
            "color": TOKENS["text"],
        },
        "colorway": PALETTE,
        "hoverlabel": {
            "bgcolor": TOKENS["surface"],
            "font_color": TOKENS["text"],
            "bordercolor": TOKENS["line"],
        },
        "legend": {"title_text": "", "orientation": "h", "y": -0.18},
        "margin": margin or {"l": 20, "r": 20, "t": 55, "b": 35},
    }
    if height is not None:
        layout["height"] = height
    figure.update_layout(**layout)
    figure.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=TOKENS["line"],
        automargin=True,
    )
    figure.update_yaxes(
        gridcolor=TOKENS["soft"],
        zeroline=False,
        linecolor=TOKENS["line"],
        automargin=True,
    )
    return figure
