"""Reusable BI chart primitives selected from the analytical question."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any, Mapping, Sequence

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.components.common import chart_card
from dashboard.components.design import (
    COMPARISON_COLOR,
    CURRENT_COLOR,
    TOKENS,
    apply_plotly_theme,
)


CHART_SELECTION_CONTRACT = {
    "quantitative_relationship": "bubble",
    "category_single_metric": "lollipop",
    "two_period_comparison": "dumbbell",
    "series_two_period_comparison": "horizontal_grouped_bar",
    "time_series_three_or_more_periods": "line",
    "mutually_exclusive_composition": "horizontal_100pct_stacked",
    "geographic_origin": "bubble_map",
    "long_category_labels": "horizontal_lollipop",
}
STANDARD_CHART_HEIGHT = 320
MIN_CHART_HEIGHT = 280
MAX_CHART_HEIGHT = 360
PLOTLY_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
    "scrollZoom": False,
}


def _height(category_count: int) -> int:
    return max(MIN_CHART_HEIGHT, min(MAX_CHART_HEIGHT, 155 + 34 * category_count))


def _number(value: float | int, suffix: str = "") -> str:
    rendered = (
        f"{int(value):,}".replace(",", ".")
        if float(value).is_integer()
        else f"{float(value):.1f}".replace(".", ",")
    )
    return f"{rendered}{suffix}"


def _signed_number(value: float | int, suffix: str = "") -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{_number(value, suffix)}"


def build_dumbbell_figure(
    rows: Sequence[Mapping[str, Any]],
    *,
    label_key: str,
    comparison_key: str,
    current_key: str,
    value_suffix: str = "",
    axis_title: str,
) -> go.Figure:
    """Compare two periods across categories without implying a time series."""

    ordered = list(rows)
    figure = go.Figure()
    for index, row in enumerate(ordered):
        comparison = float(row[comparison_key])
        current = float(row[current_key])
        figure.add_shape(
            type="line",
            x0=comparison,
            x1=current,
            y0=index,
            y1=index,
            line={"color": "#C8D0D1", "width": 3},
            layer="below",
        )
    labels = [str(row[label_key]) for row in ordered]
    comparison_values = [float(row[comparison_key]) for row in ordered]
    current_values = [float(row[current_key]) for row in ordered]
    deltas = [current - comparison for current, comparison in zip(current_values, comparison_values)]
    figure.add_trace(
        go.Scatter(
            x=comparison_values,
            y=list(range(len(ordered))),
            mode="markers+text",
            marker={"size": 10, "color": COMPARISON_COLOR},
            text=[_number(value, value_suffix) for value in comparison_values],
            textposition="middle left",
            textfont={"color": COMPARISON_COLOR},
            hovertemplate="Comparación: %{x}<extra></extra>",
            name="Comparación",
            cliponaxis=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=current_values,
            y=list(range(len(ordered))),
            mode="markers+text",
            marker={"size": 12, "color": CURRENT_COLOR},
            text=[
                f"{_number(value, value_suffix)}  (Δ {_signed_number(delta, value_suffix)})"
                for value, delta in zip(current_values, deltas)
            ],
            textposition="middle right",
            textfont={"color": TOKENS["teal_900"]},
            hovertemplate="Actual: %{x}<extra></extra>",
            name="Actual",
            cliponaxis=False,
        )
    )
    apply_plotly_theme(figure, height=_height(len(ordered)))
    figure.update_layout(showlegend=False, margin={"l": 20, "r": 115, "t": 15, "b": 40})
    figure.update_yaxes(
        tickmode="array",
        tickvals=list(range(len(labels))),
        ticktext=labels,
        autorange="reversed",
        title_text="",
    )
    figure.update_xaxes(title_text=axis_title, rangemode="tozero")
    return figure


def build_grouped_two_period_bar_figure(
    rows: Sequence[Mapping[str, Any]],
    *,
    period_key: str,
    series_key: str,
    value_key: str,
    axis_title: str,
) -> go.Figure:
    """Compare several series in two periods using restrained horizontal bars."""

    period_order = ("Comparación", "Actual")
    series_labels = list(dict.fromkeys(str(row[series_key]) for row in rows))
    values = {
        (str(row[series_key]), str(row[period_key])): float(row[value_key])
        for row in rows
    }
    colors = {
        "Comparación": COMPARISON_COLOR,
        "Actual": CURRENT_COLOR,
    }
    figure = go.Figure()
    for period in period_order:
        figure.add_trace(
            go.Bar(
                x=[values.get((series, period)) for series in series_labels],
                y=series_labels,
                orientation="h",
                name=period,
                marker={"color": colors[period]},
                width=0.28,
                hovertemplate=(
                    f"Período: {period}<br>Serie: %{{y}}<br>"
                    f"{axis_title}: %{{x:,.0f}}<extra></extra>"
                ),
            )
        )
    apply_plotly_theme(figure, height=_height(len(series_labels)))
    figure.update_layout(
        barmode="group",
        bargap=0.38,
        bargroupgap=0.12,
        legend={"orientation": "h", "y": -0.22, "title_text": ""},
        margin={"l": 20, "r": 25, "t": 15, "b": 60},
    )
    figure.update_xaxes(title_text=axis_title, rangemode="tozero")
    figure.update_yaxes(title_text="", autorange="reversed")
    return figure


def build_horizontal_category_bar_figure(
    rows: Sequence[Mapping[str, Any]],
    *,
    label_key: str,
    value_key: str,
    axis_title: str,
    color_map: Mapping[str, str] | None = None,
) -> go.Figure:
    """Render slim horizontal category bars with optional identity colors."""

    ordered = sorted(
        rows,
        key=lambda row: (float(row[value_key]), str(row[label_key]).casefold()),
    )
    labels = [str(row[label_key]) for row in ordered]
    values = [float(row[value_key]) for row in ordered]
    colors = [
        color_map.get(label, CURRENT_COLOR) if color_map else CURRENT_COLOR
        for label in labels
    ]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker={"color": colors},
            width=0.58,
            hovertemplate=(
                f"{label_key}: %{{y}}<br>{axis_title}: %{{x:,.0f}}<extra></extra>"
            ),
            showlegend=False,
        )
    )
    apply_plotly_theme(figure, height=_height(len(labels)))
    figure.update_layout(
        bargap=0.28,
        margin={"l": 20, "r": 20, "t": 15, "b": 40},
    )
    figure.update_xaxes(title_text=axis_title, rangemode="tozero")
    figure.update_yaxes(title_text="")
    return figure


def build_lollipop_figure(
    rows: Sequence[Mapping[str, Any]],
    *,
    label_key: str,
    value_key: str,
    axis_title: str,
    value_suffix: str = "",
) -> go.Figure:
    """Show one metric across sorted, fully named categories."""

    ordered = sorted(rows, key=lambda row: (float(row[value_key]), str(row[label_key])))
    labels = [str(row[label_key]) for row in ordered]
    values = [float(row[value_key]) for row in ordered]
    figure = go.Figure()
    for index, value in enumerate(values):
        figure.add_shape(
            type="line",
            x0=0,
            x1=value,
            y0=index,
            y1=index,
            line={"color": "#CBD5D6", "width": 2},
            layer="below",
        )
    figure.add_trace(
        go.Scatter(
            x=values,
            y=list(range(len(ordered))),
            mode="markers+text",
            marker={"size": 11, "color": CURRENT_COLOR},
            text=[_number(value, value_suffix) for value in values],
            textposition="middle right",
            hovertemplate="%{text}<extra></extra>",
            cliponaxis=False,
            showlegend=False,
        )
    )
    apply_plotly_theme(figure, height=_height(len(ordered)))
    figure.update_layout(margin={"l": 20, "r": 75, "t": 15, "b": 40})
    figure.update_yaxes(
        tickmode="array",
        tickvals=list(range(len(labels))),
        ticktext=labels,
        title_text="",
    )
    figure.update_xaxes(title_text=axis_title, rangemode="tozero")
    return figure


def build_100pct_stacked_figure(
    rows: Sequence[Mapping[str, Any]],
    *,
    row_key: str,
    segment_key: str,
    count_key: str,
    percentage_key: str,
    segment_order: Sequence[str],
    color_map: Mapping[str, str],
) -> go.Figure:
    """Render mutually exclusive categories as a compact horizontal composition."""

    row_labels = list(dict.fromkeys(str(row[row_key]) for row in rows))
    figure = go.Figure()
    for segment in segment_order:
        segment_rows = {
            str(row[row_key]): row
            for row in rows
            if str(row[segment_key]) == segment
        }
        percentages = [float(segment_rows[label][percentage_key]) for label in row_labels]
        counts = [int(segment_rows[label][count_key]) for label in row_labels]
        figure.add_trace(
            go.Bar(
                x=percentages,
                y=row_labels,
                orientation="h",
                name=segment,
                marker={"color": color_map[segment]},
                text=[
                    f"{percentage:.0f}% · n {count}" if percentage >= 8 else ""
                    for percentage, count in zip(percentages, counts)
                ],
                textposition="inside",
                customdata=counts,
                hovertemplate=(
                    f"{segment}<br>Porcentaje: %{{x:.1f}}%<br>Episodios: "
                    "%{customdata}<extra></extra>"
                ),
                width=0.52,
            )
        )
    apply_plotly_theme(figure, height=MIN_CHART_HEIGHT)
    figure.update_layout(
        barmode="stack",
        bargap=0.42,
        legend={"orientation": "h", "y": -0.24, "title_text": ""},
        margin={"l": 20, "r": 20, "t": 15, "b": 65},
    )
    figure.update_xaxes(title_text="Composición", range=[0, 100], ticksuffix="%")
    figure.update_yaxes(title_text="")
    return figure


def build_bubble_figure(
    rows: Sequence[Mapping[str, Any]],
    *,
    label_key: str,
    x_key: str,
    y_key: str,
    size_key: str,
    x_title: str,
    y_title: str,
) -> go.Figure:
    """Show a relationship between two quantitative aggregate measures."""

    sizes = [float(row[size_key]) for row in rows]
    max_size = max(sizes, default=1)
    size_ref = 2 * max_size / (34**2)
    figure = go.Figure(
        go.Scatter(
            x=[row[x_key] for row in rows],
            y=[row[y_key] for row in rows],
            mode="markers",
            marker={
                "size": sizes,
                "sizemode": "area",
                "sizeref": size_ref,
                "sizemin": 7,
                "color": CURRENT_COLOR,
                "opacity": 0.68,
                "line": {"color": TOKENS["teal_900"], "width": 1},
            },
            text=[str(row[label_key]) for row in rows],
            customdata=[[row[size_key]] for row in rows],
            hovertemplate=(
                "%{text}<br>"
                + x_title
                + ": %{x}<br>"
                + y_title
                + ": %{y}<br>Abiertos: %{customdata[0]}<extra></extra>"
            ),
            showlegend=False,
        )
    )
    apply_plotly_theme(figure, height=STANDARD_CHART_HEIGHT)
    figure.update_layout(margin={"l": 20, "r": 20, "t": 15, "b": 45})
    figure.update_xaxes(title_text=x_title, rangemode="tozero")
    figure.update_yaxes(title_text=y_title, rangemode="tozero")
    return figure


def _rows_to_csv(rows: Sequence[Mapping[str, Any]]) -> bytes:
    if not rows:
        return b""
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def render_chart_card(
    figure: go.Figure,
    rows: Sequence[Mapping[str, Any]],
    *,
    title: str,
    subtitle: str,
    key: str,
    file_name: str | None = None,
) -> None:
    """Render a compact chart with an accessible table and matching CSV."""

    with chart_card(title, subtitle):
        st.plotly_chart(
            figure,
            width="stretch",
            config=PLOTLY_CONFIG,
            key=f"prototype_chart_{key}",
        )
        with st.expander(f"Tabla accesible · {title}"):
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.download_button(
                "Descargar tabla agregada (CSV)",
                _rows_to_csv(rows),
                file_name=file_name or f"hec_{key}.csv",
                mime="text/csv",
                key=f"prototype_download_{key}",
            )
