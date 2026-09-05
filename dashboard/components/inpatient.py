"""Directorial presentation for the isolated HEC inpatient reference."""

from __future__ import annotations

import csv
from io import StringIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.components.charts import PLOTLY_CONFIG
from dashboard.components.common import (
    MetricCard,
    chart_card,
    render_badges,
    render_compact_metric_cards,
)
from dashboard.components.design import TOKENS, apply_plotly_theme
from hec_dashboard.inpatient_reference import (
    InpatientIndicatorEngine,
    InpatientIndicatorResult,
)


PRIMARY_INPATIENT_IDS = (
    "inpatient_occupancy_pct",
    "inpatient_average_length_of_stay_days",
    "inpatient_discharges_total",
    "inpatient_crude_lethality_pct",
)
TREND_IDS = (
    "inpatient_occupancy_pct",
    "inpatient_average_length_of_stay_days",
    "inpatient_discharges_total",
    "inpatient_crude_lethality_pct",
)
MONTH_LABELS = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


def _value_text(result: InpatientIndicatorResult) -> str:
    if result.status != "available" or result.value is None:
        return {
            "zero_denominator": "Sin denominador válido",
            "unavailable": "No disponible",
        }.get(result.status, "No disponible")
    if result.unit == "percentage":
        return f"{float(result.value):.1f}%".replace(".", ",")
    if result.unit == "days":
        return f"{float(result.value):.1f} días".replace(".", ",")
    if result.unit == "beds":
        return f"{float(result.value):.1f}".replace(".", ",")
    return f"{int(result.value):,}".replace(",", ".")


def _rows_to_csv(rows: list[dict[str, object]]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _monthly_rows(
    engine: InpatientIndicatorEngine, indicator_id: str
) -> list[dict[str, object]]:
    rows = []
    for result in engine.monthly_series(indicator_id):
        rows.append(
            {
                "Mes": MONTH_LABELS[result.period_start.month],
                "Mes inicio": result.period_start.isoformat(),
                "Indicador": result.display_name_es,
                "Valor": result.value,
                "Unidad": result.unit,
                "Numerador": result.numerator,
                "Denominador": result.denominator,
                "Estado": result.status,
            }
        )
    return rows


def render_inpatient_reference(role_id: str) -> None:
    """Render a source-isolated closed-care panel for an authorized role."""

    engine = InpatientIndicatorEngine.from_repo(role_id)
    dataset = engine.dataset
    results = {item.indicator_id: item for item in engine.calculate_all()}

    st.subheader("Hospitalización y camas")
    st.markdown(
        "<p class=\"hec-section-intro\">Referencia histórica agregada del Hospital "
        "El Carmen. Describe la hospitalización de 2025 y se mantiene separada de "
        "la actividad ambulatoria simulada de 2026.</p>",
        unsafe_allow_html=True,
    )
    render_badges(
        "Período fijo: enero–diciembre de 2025",
        "Sin comparación interanual",
        source=dataset.contract["source_badge"],
    )

    render_compact_metric_cards(
        [
            MetricCard(
                label=results[indicator_id].display_name_es,
                value=_value_text(results[indicator_id]),
                subtitle="Referencia descriptiva · sin meta ni delta",
            )
            for indicator_id in PRIMARY_INPATIENT_IDS
        ]
    )
    average_beds = results["inpatient_average_beds"]
    with st.container(border=True):
        st.markdown("**Contexto de capacidad**")
        st.markdown(
            f"Promedio de camas disponibles: **{_value_text(average_beds)} camas** "
            "(días cama disponibles / 365)."
        )
        st.caption(
            "No se aplica semáforo: la fuente no configura una meta HEC con definición comparable."
        )

    trend_labels = {
        item_id: results[item_id].display_name_es for item_id in TREND_IDS
    }
    selected_indicator = st.selectbox(
        "Indicador de tendencia mensual",
        TREND_IDS,
        format_func=trend_labels.get,
        key=f"inpatient_trend_{role_id}",
    )
    trend_rows = _monthly_rows(engine, selected_indicator)
    selected_result = results[selected_indicator]
    with chart_card(
        f"¿Cómo varió {selected_result.display_name_es.casefold()} durante 2025?",
        "Serie HEC observada y recalculada desde primitivas mensuales; no es una distribución artificial del total anual.",
    ):
        figure = go.Figure(
            go.Scatter(
                x=[row["Mes"] for row in trend_rows],
                y=[row["Valor"] for row in trend_rows],
                mode="lines+markers",
                line={"color": TOKENS["teal_500"], "width": 3},
                marker={
                    "size": 7,
                    "color": TOKENS["surface"],
                    "line": {"color": TOKENS["teal_500"], "width": 2},
                },
                hovertemplate=(
                    "%{x} 2025<br>Valor: %{y}<extra>Hospital El Carmen</extra>"
                ),
                name=selected_result.display_name_es,
            )
        )
        apply_plotly_theme(
            figure,
            height=340,
            margin={"l": 20, "r": 20, "t": 25, "b": 45},
        )
        figure.update_layout(showlegend=False)
        figure.update_yaxes(title_text=selected_result.display_name_es)
        st.plotly_chart(
            figure,
            width="stretch",
            config=PLOTLY_CONFIG,
            key=f"inpatient_monthly_chart_{role_id}_{selected_indicator}",
        )
        with st.expander("Tabla accesible y descarga de la serie mensual"):
            st.dataframe(pd.DataFrame(trend_rows), hide_index=True, width="stretch")
            st.download_button(
                "Descargar serie mensual HEC (CSV)",
                _rows_to_csv(trend_rows),
                file_name=f"hec_2025_{selected_indicator}.csv",
                mime="text/csv",
                key=f"download_inpatient_{role_id}_{selected_indicator}",
            )

    st.warning(
        "La letalidad presentada es bruta y no está ajustada por riesgo o complejidad. "
        "No debe usarse para rankings, atribución causal ni comparaciones de desempeño."
    )
    with st.expander("Fuente, primitivas y cálculos", expanded=False):
        annual = dataset.annual
        st.dataframe(
            [
                {
                    "Período": "2025",
                    "Días cama disponibles": annual["available_bed_days"],
                    "Días cama ocupados": annual["occupied_bed_days"],
                    "Días de estada": annual["total_stay_days"],
                    "Egresos": annual["discharges"],
                    "Egresos por defunción": annual["death_discharges"],
                }
            ],
            hide_index=True,
            width="stretch",
        )
        st.markdown(
            "- Ocupación = días cama ocupados / días cama disponibles.\n"
            "- Estada promedio = días de estada / egresos.\n"
            "- Letalidad bruta = egresos por defunción / egresos."
        )
        st.caption(
            "Fuente primaria curada: registro HEC suministrado por el usuario. "
            "Año de desempeño y serie mensual corroborados por un artefacto docente local; "
            "corte declarado 16-04-2026. Evidencia secundaria, no base MINSAL original."
        )
        st.caption(
            "Cerrillos no está presente en esta fuente; su ausencia no representa actividad "
            "ni capacidad igual a cero."
        )
