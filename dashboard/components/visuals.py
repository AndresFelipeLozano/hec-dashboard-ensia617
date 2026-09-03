"""Accessible Plotly/MapLibre presentation for governed Day 5 aggregates."""

from __future__ import annotations

from datetime import date
from textwrap import wrap
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from hec_dashboard.data_ingestion import CandidateDataset
from hec_dashboard.app_config import specialty_label
from hec_dashboard.visual_analytics import (
    HEC_MARKER_SIZE,
    HEC_MARKER_SYMBOL,
    aging_distribution,
    center_waitlist_context,
    diagnosis_composition_by_establishment,
    diagnosis_options,
    hec_marker,
    origin_bubbles,
    prestation_composition,
    prioritized_findings,
    referring_center_diagnoses,
    referring_center_prestations,
    referring_center_specialties,
    role_activity_composition,
    role_activity_trend,
    rows_to_csv,
    scoped_network_rows,
    scoped_waitlist_rows,
    specialty_pressure,
    status_flow,
    waitlist_indicator_trend,
)


PALETTE = ["#0B6B69", "#2F80ED", "#F2C94C", "#EB5757", "#6C5CE7"]


def _chart_and_table(
    figure: go.Figure,
    rows: list[dict[str, Any]],
    *,
    title: str,
    key: str,
) -> None:
    responsive_title = "<br>".join(wrap(title, width=36))
    figure.update_layout(
        title={"text": responsive_title, "font": {"size": 17}},
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        legend_title_text="",
        font={"family": "Arial, sans-serif", "size": 13},
        colorway=PALETTE,
    )
    figure.update_xaxes(automargin=True)
    figure.update_yaxes(automargin=True)
    category_values: list[str] = []
    for trace in figure.data:
        trace_values = getattr(trace, "y", None)
        if trace_values is None:
            continue
        for value in trace_values:
            if isinstance(value, str) and value not in category_values:
                category_values.append(value)
    if any(len(value) > 18 for value in category_values):
        figure.update_layout(margin={"l": 175, "r": 10, "t": 75, "b": 25})
        figure.update_yaxes(
            title_text="",
            tickmode="array",
            tickvals=category_values,
            ticktext=[
                value if len(value) <= 16 else f"{value[:15].rstrip()}…"
                for value in category_values
            ],
        )
    st.plotly_chart(figure, width="stretch", key=f"chart_{key}")
    with st.expander(f"Tabla accesible · {title}"):
        st.dataframe(rows, hide_index=True, width="stretch")
        st.download_button(
            "Descargar tabla agregada (CSV)",
            rows_to_csv(rows),
            file_name=f"hec_{key}.csv",
            mime="text/csv",
            key=f"download_{key}",
        )


def render_findings(rows: list[dict[str, Any]]) -> None:
    st.subheader("Hallazgos priorizados")
    findings = prioritized_findings(rows)
    if not findings:
        st.caption("No hay evidencia suficiente para emitir hallazgos en este contexto.")
        return
    for index, finding in enumerate(findings, start=1):
        with st.container(border=True):
            st.markdown(f"**{index}. {finding['Hallazgo']}**")
            st.caption(finding["Límite interpretativo"])
            st.write(f"Acción sugerida: {finding['Acción de revisión']}")


def render_waitlist_analytics(
    dataset: CandidateDataset,
    current: tuple[date, date],
    previous: tuple[date, date],
    role_context: dict[str, Any],
) -> None:
    rows = scoped_waitlist_rows(dataset, current, role_context)
    if not rows:
        st.warning(
            "La carga activa no contiene LISTA_ESPERA_AMB para este contexto. "
            "La ausencia se informa como no disponible y no como cero."
        )
        return
    trend = waitlist_indicator_trend(dataset, current, previous, role_context)
    count_trend = [row for row in trend if row["Unidad"] == "Episodios" and row["Estado"] == "available"]
    days_trend = [row for row in trend if row["Unidad"] == "Días" and row["Estado"] == "available"]
    if count_trend:
        count_figure = px.line(
            pd.DataFrame(count_trend),
            x="Período",
            y="Valor",
            color="Indicador",
            markers=True,
            color_discrete_sequence=PALETTE,
        )
        _chart_and_table(
            count_figure,
            count_trend,
            title="Tendencia gobernada de episodios abiertos",
            key=f"tendencia_espera_conteos_{role_context['role_id']}",
        )
    if days_trend:
        days_figure = px.line(
            pd.DataFrame(days_trend),
            x="Período",
            y="Valor",
            color="Indicador",
            markers=True,
            color_discrete_sequence=PALETTE,
        )
        _chart_and_table(
            days_figure,
            days_trend,
            title="Tendencia gobernada de percentil 75",
            key=f"tendencia_espera_dias_{role_context['role_id']}",
        )
    render_findings(rows)
    aging = aging_distribution(rows)
    aging_figure = px.bar(
        pd.DataFrame(aging),
        x="Tramo de antigüedad",
        y="Episodios",
        color="Cola",
        barmode="group",
        color_discrete_sequence=PALETTE,
    )
    _chart_and_table(
        aging_figure,
        aging,
        title="Antigüedad de episodios abiertos",
        key="antiguedad_lista_espera",
    )

    flow = status_flow(rows)
    flow_figure = px.bar(
        pd.DataFrame(flow),
        x="Estado",
        y="Episodios",
        color="Cola",
        barmode="group",
        color_discrete_sequence=PALETTE,
    )
    _chart_and_table(
        flow_figure,
        flow,
        title="Flujo y resolución al corte",
        key="flujo_lista_espera",
    )

    composition = prestation_composition(rows)
    composition_figure = px.bar(
        pd.DataFrame(composition),
        x="Episodios",
        y="Prestación solicitada",
        orientation="h",
        color_discrete_sequence=[PALETTE[0]],
    )
    _chart_and_table(
        composition_figure,
        composition,
        title="Composición por prestación solicitada",
        key="prestaciones_lista_espera",
    )

    if not str(role_context.get("role_id", "")).startswith("professional_"):
        pressure = specialty_pressure(rows)[:15]
        pressure_figure = px.bar(
            pd.DataFrame(pressure),
            x="Especialidad",
            y=">90 días",
            color="P75 días",
            color_continuous_scale=["#D9F2F0", "#0B6B69", "#7A1F2B"],
        )
        _chart_and_table(
            pressure_figure,
            pressure,
            title="Especialidades con mayor antigüedad",
            key="presion_especialidades",
        )


def render_role_activity_analytics(
    dataset: CandidateDataset,
    current: tuple[date, date],
    previous: tuple[date, date],
    role_context: dict[str, Any],
) -> None:
    role_id = role_context["role_id"]
    title_by_role = {
        "director": "Tendencia institucional de demanda validada",
        "medical_director": "Tendencia clínico-operacional institucional",
        "service_chief_clinical": "Tendencia ambulatoria del servicio",
        "service_chief_surgical": "Tendencia quirúrgica del servicio",
        "professional_clinical": "Tendencia de actividad clínica del perfil simulado",
        "professional_surgical": "Tendencia de actividad quirúrgica del perfil simulado",
    }
    trend = role_activity_trend(dataset, current, previous, role_context)
    if not trend:
        st.warning("No hay agregados de actividad disponibles para este contexto.")
        return
    trend_figure = px.bar(
        pd.DataFrame(trend),
        x="Período",
        y="Eventos",
        color="Serie",
        barmode="group",
        color_discrete_sequence=PALETTE,
    )
    _chart_and_table(
        trend_figure,
        trend,
        title=title_by_role[role_id],
        key=f"actividad_tendencia_{role_id}",
    )

    composition = role_activity_composition(dataset, current, role_context)
    if not composition:
        st.caption("No hay composición publicable para el período seleccionado.")
        return
    category = next(key for key in composition[0] if key != "Eventos")
    composition_figure = px.bar(
        pd.DataFrame(composition),
        x="Eventos",
        y=category,
        orientation="h",
        color_discrete_sequence=[PALETTE[0]],
    )
    _chart_and_table(
        composition_figure,
        composition,
        title=f"Composición actual por {category.lower()}",
        key=f"actividad_composicion_{role_id}",
    )


def render_origin_map(
    dataset: CandidateDataset,
    current: tuple[date, date],
    previous: tuple[date, date],
    role_context: dict[str, Any],
) -> None:
    st.subheader("Red de derivación hacia el HEC")
    st.caption(
        "Análisis agregado de datos completamente simulados. Una burbuja representa un "
        "establecimiento DEIS y nunca una persona; se suprimen celdas con n < 10. "
        "El marcador del Hospital El Carmen es contextual y no representa demanda."
    )
    role_id = role_context["role_id"]
    is_director = role_id in {"director", "medical_director"}
    context_key = f"{role_id}_{role_context.get('professional_lens') or 'institutional'}"
    institutional_context = dict(role_context)
    if is_director:
        institutional_context["service_id"] = None
        institutional_context["specialty_id"] = None
    institutional_context["referral_diagnosis_id"] = None
    scoped_institutional = scoped_network_rows(
        dataset, current, institutional_context
    )
    specialty_ids = sorted(
        {row["specialty_id"] for row in scoped_institutional},
        key=lambda value: specialty_label(value).casefold(),
    )
    if is_director:
        mode = st.radio(
            "Modo de análisis de red",
            ["Red institucional", "Especialidad seleccionada", "Centro derivador"],
            horizontal=True,
            key=f"map_mode_{context_key}",
        )
    else:
        mode = "Especialidad seleccionada"
        if role_context.get("specialty_id"):
            st.caption(
                f"Especialidad heredada del rol: **{specialty_label(role_context['specialty_id'])}**. "
                "No se habilitan especialidades incompatibles."
            )
        else:
            st.caption(
                "Seleccione una especialidad compatible con el servicio activo. "
                "No se habilitan especialidades de otros servicios."
            )

    map_context = dict(role_context)
    selected_specialty_id = role_context.get("specialty_id")
    if is_director and mode in {"Especialidad seleccionada", "Centro derivador"}:
        default_index = (
            specialty_ids.index("urologia") if "urologia" in specialty_ids else 0
        )
        selected_specialty_id = st.selectbox(
            "Especialidad de destino",
            specialty_ids,
            index=default_index,
            format_func=specialty_label,
            key=f"map_specialty_{context_key}_{mode}",
        )
        map_context["specialty_id"] = selected_specialty_id
        matching = next(
            row for row in scoped_institutional if row["specialty_id"] == selected_specialty_id
        )
        map_context["service_id"] = matching["service_id"]
    elif is_director:
        map_context["service_id"] = None
        map_context["specialty_id"] = None
    elif selected_specialty_id is None:
        selected_specialty_id = st.selectbox(
            "Especialidad del servicio",
            specialty_ids,
            format_func=specialty_label,
            key=f"map_specialty_{context_key}_{mode}",
        )
        map_context["specialty_id"] = selected_specialty_id

    scoped = scoped_network_rows(dataset, current, map_context)
    prestation_labels = {
        "consulta_nueva": "Consulta nueva",
        "control_especialidad": "Control de especialidad",
        "evaluacion_preoperatoria": "Evaluación preoperatoria",
        "procedimiento_ambulatorio": "Procedimiento ambulatorio",
    }
    prestation_options = ["Todas", *sorted({row["requested_prestation"] for row in scoped})]
    selected_prestation = st.selectbox(
        "Prestación incluida en el mapa",
        prestation_options,
        format_func=lambda value: "Todas las prestaciones" if value == "Todas" else prestation_labels[value],
        key=f"map_prestation_{context_key}_{mode}",
    )
    map_context["prestation_type"] = (
        None if selected_prestation == "Todas" else selected_prestation
    )
    diagnosis_rows = scoped_network_rows(dataset, current, map_context)
    available_diagnoses = diagnosis_options(diagnosis_rows)
    selected_diagnosis_id: str | None = None
    if mode != "Red institucional":
        if available_diagnoses:
            diagnosis_ids = [
                item["diagnosis_group_id"] for item in available_diagnoses
            ]
            diagnosis_labels = {
                item["diagnosis_group_id"]: item["label_es"]
                for item in available_diagnoses
            }
            selected_diagnosis = st.selectbox(
                "Diagnóstico o motivo de derivación simulado",
                ["Todos", *diagnosis_ids],
                format_func=lambda value: (
                    "Todos los motivos simulados"
                    if value == "Todos"
                    else diagnosis_labels[value]
                ),
                key=f"map_diagnosis_{context_key}_{mode}_{selected_specialty_id}",
            )
            if selected_diagnosis != "Todos":
                selected_diagnosis_id = selected_diagnosis
        else:
            st.selectbox(
                "Diagnóstico o motivo de derivación simulado",
                ["No disponible en esta carga heredada"],
                disabled=True,
                key=f"map_diagnosis_legacy_{context_key}_{mode}",
            )
            st.caption(
                "La carga activa no contiene la dimensión diagnóstica. Su ausencia se "
                "presenta como no disponible, nunca como cero."
            )
    map_context["referral_diagnosis_id"] = selected_diagnosis_id
    map_context["map_mode"] = mode
    rows = origin_bubbles(dataset, current, previous, map_context)
    if not rows:
        st.warning("No hay celdas geográficas publicables para los filtros actuales.")
        return
    color_options = (
        ["Especialidad predominante", "Tendencia", "Volumen"]
        if mode == "Red institucional"
        else [
            *(["Diagnóstico predominante"] if available_diagnoses else []),
            "Participación de especialidad",
            "Tendencia",
        ]
    )
    color_mode = st.radio(
        "Color de burbuja",
        color_options,
        horizontal=True,
        key=f"map_color_{context_key}_{mode}",
    )
    color_column = {
        "Volumen": "Episodios",
        "Especialidad predominante": "Especialidad predominante",
        "Diagnóstico predominante": "Diagnóstico predominante",
        "Participación de especialidad": "Participación de especialidad en centro (%)",
        "Tendencia": "Tendencia",
    }[color_mode]
    map_context["color_mode"] = color_mode
    selected_specialty_label = (
        specialty_label(selected_specialty_id)
        if selected_specialty_id
        else "Todas las especialidades"
    )
    map_title = (
        "Red de derivación hacia el HEC"
        if mode == "Red institucional"
        else f"Derivaciones a {selected_specialty_label} por establecimiento"
    )
    if selected_diagnosis_id:
        diagnosis_label = next(
            item["label_es"]
            for item in available_diagnoses
            if item["diagnosis_group_id"] == selected_diagnosis_id
        )
        map_title = f"{diagnosis_label} · {selected_specialty_label}"
    st.markdown(f"#### {map_title}")
    st.caption(
        f"Rol: {role_id} · Especialidad: {selected_specialty_label} · "
        f"Actual {current[0].isoformat()}–{current[1].isoformat()} · "
        f"Comparación {previous[0].isoformat()}–{previous[1].isoformat()}"
    )
    try:
        frame = pd.DataFrame(rows)
        figure = px.scatter_map(
            frame,
            lat="Latitud",
            lon="Longitud",
            size="Episodios",
            color=color_column,
            hover_name="Establecimiento",
            hover_data={
                "Código DEIS": True,
                "Comuna": True,
                "Episodios": True,
                "Participación (%)": ":.2f",
                "Abiertos": True,
                "Variación": True,
                "Tendencia": True,
                "Prestación principal": True,
                "Especialidad seleccionada": True,
                "Especialidad predominante": True,
                "Top tres especialidades": True,
                "Diagnóstico predominante": True,
                "Participación de especialidad en centro (%)": ":.2f",
                "Período actual": True,
                "Período comparación": True,
                "Latitud": False,
                "Longitud": False,
            },
            size_max=38,
            zoom=9.6,
            map_style="carto-positron",
            color_discrete_sequence=PALETTE,
            color_continuous_scale="Tealrose",
        )
        hospital = hec_marker()
        figure.add_trace(
            go.Scattermap(
                lat=[hospital["Latitud"]],
                lon=[hospital["Longitud"]],
                mode="markers",
                marker={
                    "size": HEC_MARKER_SIZE,
                    "color": "#111827",
                    "symbol": HEC_MARKER_SYMBOL,
                },
                text=[hospital["Establecimiento"]],
                hovertemplate="Hospital El Carmen<extra></extra>",
                name="Hospital El Carmen",
            )
        )
        figure.update_layout(
            margin={"l": 0, "r": 0, "t": 10, "b": 0},
            legend_title_text="",
            height=540,
        )
        st.plotly_chart(
            figure,
            width="stretch",
            key=f"referral_origin_map_{context_key}_{mode}_{selected_specialty_id}_{selected_diagnosis_id}_{color_mode}",
        )
    except Exception as exc:  # tile/render failures must not hide the evidence table
        st.warning(f"El mapa no pudo representarse; la tabla sigue disponible. ({exc})")
    with st.expander("Tabla accesible y descargable del mapa", expanded=True):
        table_rows = [
            {key: value for key, value in row.items() if key not in {"Latitud", "Longitud"}}
            for row in rows
        ]
        st.dataframe(table_rows, hide_index=True, width="stretch")
        st.download_button(
            "Descargar orígenes agregados (CSV)",
            rows_to_csv(table_rows),
            file_name="hec_origenes_agregados.csv",
            mime="text/csv",
            key=f"download_map_table_{context_key}_{mode}_{selected_specialty_id}_{selected_diagnosis_id}",
        )

    top_centers = [
        {
            "Establecimiento": row["Establecimiento"],
            "Código DEIS": row["Código DEIS"],
            "Episodios": row["Episodios"],
            "Variación": row["Variación"],
            "Tendencia": row["Tendencia"],
        }
        for row in rows[:10]
    ]
    top_figure = px.bar(
        pd.DataFrame(top_centers),
        x="Episodios",
        y="Establecimiento",
        orientation="h",
        color="Tendencia",
        color_discrete_map={
            "Aumento": "#B42318",
            "Estable": "#667085",
            "Disminución": "#0B6B69",
        },
    )
    _chart_and_table(
        top_figure,
        top_centers,
        title=f"Principales establecimientos derivadores · {selected_specialty_label}",
        key=f"top_centers_{context_key}_{mode}_{selected_specialty_id}_{selected_diagnosis_id}",
    )

    if selected_specialty_id and available_diagnoses:
        composition_context = dict(map_context)
        composition_context["referral_diagnosis_id"] = None
        diagnosis_composition = diagnosis_composition_by_establishment(
            dataset, current, composition_context
        )
        if diagnosis_composition:
            top_codes = {row["Código DEIS"] for row in rows[:6]}
            diagnosis_composition = [
                row
                for row in diagnosis_composition
                if row["Código DEIS"] in top_codes
            ]
            composition_figure = px.bar(
                pd.DataFrame(diagnosis_composition),
                x="Episodios",
                y="Establecimiento",
                color="Diagnóstico o motivo de derivación simulado",
                orientation="h",
                barmode="stack",
                color_discrete_sequence=PALETTE,
            )
            _chart_and_table(
                composition_figure,
                diagnosis_composition,
                title=(
                    "Composición diagnóstica simulada por establecimiento · "
                    f"{selected_specialty_label}"
                ),
                key=f"diagnosis_composition_{context_key}_{selected_specialty_id}",
            )

    center_options = [row["Código DEIS"] for row in rows]
    center_labels = {
        row["Código DEIS"]: row["Establecimiento"] for row in rows
    }
    selected_center = st.selectbox(
        "Establecimiento derivador para profundizar",
        center_options,
        format_func=lambda value: f"{center_labels[value]} · {value}",
        key=f"map_center_{context_key}_{mode}_{selected_specialty_id}_{selected_diagnosis_id}",
    )
    st.markdown(f"#### Perfil de derivaciones desde {center_labels[selected_center]}")
    selected_map_row = next(
        row for row in rows if row["Código DEIS"] == selected_center
    )
    st.dataframe(
        [
            {
                "Volumen actual": selected_map_row["Episodios"],
                "Variación Q2 vs Q1": selected_map_row["Variación"],
                "Tendencia": selected_map_row["Tendencia"],
            }
        ],
        hide_index=True,
        width="stretch",
    )

    center_specialty_context = dict(map_context)
    if is_director:
        specialty_breakdown = referring_center_specialties(
            dataset,
            current,
            previous,
            institutional_context,
            selected_center,
        )
        if specialty_breakdown:
            specialty_figure = px.bar(
                pd.DataFrame(specialty_breakdown),
                x="Actual",
                y="Especialidad",
                orientation="h",
                color="Variación",
                color_continuous_scale="Tealrose",
            )
            _chart_and_table(
                specialty_figure,
                specialty_breakdown,
                title="Especialidades derivadas desde el centro seleccionado",
                key=f"center_specialties_{context_key}_{selected_center}",
            )
            center_specialty_ids = [
                row["Especialidad ID"] for row in specialty_breakdown
            ]
            drilldown_specialty = st.selectbox(
                "Especialidad dentro del centro seleccionado",
                center_specialty_ids,
                index=(
                    center_specialty_ids.index(selected_specialty_id)
                    if selected_specialty_id in center_specialty_ids
                    else 0
                ),
                format_func=specialty_label,
                key=f"center_specialty_{context_key}_{selected_center}_{mode}",
            )
            center_specialty_context["specialty_id"] = drilldown_specialty
            matching_center_row = next(
                row
                for row in scoped_institutional
                if row["specialty_id"] == drilldown_specialty
            )
            center_specialty_context["service_id"] = matching_center_row["service_id"]

    diagnosis_breakdown = referring_center_diagnoses(
        dataset, current, center_specialty_context, selected_center
    )
    if diagnosis_breakdown:
        diagnosis_figure = px.bar(
            pd.DataFrame(diagnosis_breakdown),
            x="Episodios",
            y="Diagnóstico o motivo de derivación simulado",
            orientation="h",
            color_discrete_sequence=[PALETTE[0]],
        )
        _chart_and_table(
            diagnosis_figure,
            diagnosis_breakdown,
            title="Diagnósticos o motivos de derivación simulados del centro",
            key=f"center_diagnoses_{context_key}_{selected_center}_{center_specialty_context.get('specialty_id')}",
        )
    else:
        st.info(
            "Diagnóstico o motivo de derivación simulado: no disponible para este "
            "centro y especialidad; no se interpreta como cero."
        )

    prestations = referring_center_prestations(
        dataset, current, center_specialty_context, selected_center
    )
    if prestations:
        prestation_figure = px.bar(
            pd.DataFrame(prestations),
            x="Episodios",
            y="Prestación solicitada",
            orientation="h",
            color_discrete_sequence=[PALETTE[1]],
        )
        _chart_and_table(
            prestation_figure,
            prestations,
            title="Prestaciones solicitadas desde el centro",
            key=f"center_prestations_{context_key}_{selected_center}_{center_specialty_context.get('specialty_id')}",
        )

    queue_context = center_waitlist_context(
        dataset, current, center_specialty_context, selected_center
    )
    st.caption(
        "Contexto ambulatorio de consulta nueva y control; la lista quirúrgica se "
        "mantiene separada."
    )
    st.dataframe(queue_context, hide_index=True, width="stretch")
    if role_id.startswith("professional_"):
        st.info(
            "Esta vista describe la red agregada de la especialidad del perfil simulado. "
            "No atribuye derivaciones a una persona ni constituye un ranking profesional."
        )
