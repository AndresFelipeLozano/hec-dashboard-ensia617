"""Role-specific Day 5 dashboard with governed visual analytics."""

from __future__ import annotations

from datetime import date

import streamlit as st

from dashboard.components.common import (
    render_interpretation,
    render_kpi_cards,
    render_simulation_notice,
)
from dashboard.components.visuals import (
    render_origin_map,
    render_role_activity_analytics,
    render_waitlist_analytics,
)
from hec_dashboard.app_config import (
    get_indicator_definition,
    get_role_definition,
    get_ui_view,
    secondary_indicator_ids,
)
from hec_dashboard.app_state import Keys
from hec_dashboard.presentation import (
    build_indicator_presentations,
    build_mixed_presentations,
    build_role_presentation,
)


PERIODS = {
    "Q2 2026": (date(2026, 4, 1), date(2026, 6, 30)),
    "Q1 2026": (date(2026, 1, 1), date(2026, 3, 31)),
}

PREVIOUS_PERIODS = {
    "Q2 2026": PERIODS["Q1 2026"],
    "Q1 2026": (date(2025, 10, 1), date(2025, 12, 31)),
}


def _render_group(title: str, cards) -> None:
    st.subheader(title)
    render_kpi_cards(cards)
    render_interpretation(cards)


def _render_secondary(cards) -> None:
    st.subheader("Indicadores complementarios de acceso")
    st.dataframe(
        [
            {
                "Indicador": card.label_es,
                "Valor": card.value_text,
                "Comparación": card.previous_text or "No disponible",
                "Estado": card.status_label_es,
                "n válido": card.valid_n,
            }
            for card in cards
        ],
        hide_index=True,
        width="stretch",
    )
    render_interpretation(cards)


def _render_data_context(dataset) -> None:
    summary = dataset.validation_summary
    rows = [
        {"Hoja": sheet, "Filas activas": len(values)}
        for sheet, values in dataset.tables.items()
    ]
    st.subheader("Actividad y calidad del conjunto activo")
    st.markdown(f"**Registros aceptados:** {summary.get('accepted_rows', 0):,}")
    st.caption(
        f"Aceptación: {summary.get('accepted_record_pct', 'No disponible')}% · "
        f"Cuarentena: {summary.get('rejected_rows', 0)} · "
        f"Contrato: {dataset.metadata.get('contract_version')}"
    )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.info(
        "Las tablas de esta vista son agregadas. No existe navegación a pacientes, "
        "direcciones ni identificadores reales."
    )


def _render_definitions(indicator_ids: list[str]) -> None:
    st.subheader("Definiciones y denominadores")
    definitions = []
    for indicator_id in dict.fromkeys(indicator_ids):
        item = get_indicator_definition(indicator_id)
        definitions.append(
            {
                "Indicador": item["display_name_es"],
                "Definición": item["definition"],
                "Numerador": item["numerator"],
                "Denominador": item["denominator"] or "No aplica",
                "Unidad": item["unit"],
                "n mínimo": item["minimum_valid_n"],
            }
        )
    st.dataframe(definitions, hide_index=True, width="stretch")
    st.caption(
        "Los episodios de consulta nueva se miden desde queue_entry_date; los "
        "controles desde control_due_date. La lista quirúrgica permanece separada."
    )


def render() -> None:
    context = st.session_state.get(Keys.ROLE_CONTEXT)
    dataset = st.session_state.get(Keys.ACTIVE_DATASET)
    if not context:
        st.session_state[Keys.PENDING_NAVIGATION] = "landing"
        st.rerun()
    if dataset is None:
        st.error("No existe un dataset activo validado para calcular el dashboard.")
        return
    role_id = context["role_id"]
    view = get_ui_view(role_id)
    st.header(view["page_title_es"])
    render_simulation_notice()
    if role_id.startswith("professional_"):
        st.caption(
            f"Especialidad: {context['specialty_context_label']} · "
            f"Perfil: {context['professional_short_label']}"
        )
    st.caption(
        f"Dataset {dataset.metadata.get('dataset_id')} · "
        f"Fuente: {st.session_state.get(Keys.ACTIVE_SOURCE_MODE)}"
    )
    period_name = st.selectbox(
        "Período actual",
        list(PERIODS),
        index=0,
        help="La comparación usa el trimestre inmediatamente anterior disponible.",
        key="dashboard_period",
    )
    current = PERIODS[period_name]
    previous = PREVIOUS_PERIODS[period_name]
    st.session_state[Keys.SELECTED_CURRENT_PERIOD] = current
    st.session_state[Keys.SELECTED_PREVIOUS_PERIOD] = previous
    st.caption(
        f"Comparación: {previous[0].strftime('%d-%m-%Y')} a "
        f"{previous[1].strftime('%d-%m-%Y')}. Los filtros estrechos no se amplían automáticamente."
    )

    kwargs = {
        "service_id": context.get("service_id"),
        "specialty_id": context.get("specialty_id"),
        "simulated_profile_key": context.get("simulated_profile_key"),
    }
    effective_role_id = role_id
    if role_id == "professional_mixed":
        with st.spinner("Calculando lentes profesionales…"):
            groups = build_mixed_presentations(
                dataset,
                current,
                previous,
                context["simulated_profile_key"],
                lens_contexts=context["professional_lens_contexts"],
            )
        lens = st.radio(
            "Lente profesional",
            ["clinical", "surgical"],
            format_func=lambda value: (
                "Actividad ambulatoria/clínica"
                if value == "clinical"
                else "Actividad quirúrgica/procedimental"
            ),
            horizontal=False,
            key="dashboard_mixed_lens",
        )
        effective_role_id = (
            "professional_clinical" if lens == "clinical" else "professional_surgical"
        )
        primary_cards = groups[lens]
    else:
        with st.spinner("Calculando indicadores…"):
            primary_cards = build_role_presentation(
                role_id, dataset, current, previous, **kwargs
            )

    secondary_ids = list(secondary_indicator_ids(effective_role_id))
    visual_context = {
        **context,
        "role_id": effective_role_id,
        "professional_lens": (
            lens if role_id == "professional_mixed" else context.get("professional_lens")
        ),
    }
    if role_id == "professional_mixed":
        lens_context = context["professional_lens_contexts"][lens]
        visual_context["service_id"] = lens_context["service_id"]
        visual_context["specialty_id"] = lens_context["specialty_id"]
    with st.spinner("Preparando analítica visual…"):
        secondary_cards = build_indicator_presentations(
            secondary_ids,
            effective_role_id,
            dataset,
            current,
            previous,
            **kwargs,
        )
    tabs = st.tabs(
        [
            "Resumen",
            "Acceso y listas de espera",
            "Origen territorial",
            "Actividad y calidad",
            "Datos y definiciones",
        ]
    )
    with tabs[0]:
        primary_title = "Indicadores primarios"
        if role_id == "professional_mixed":
            primary_title = (
                "Actividad ambulatoria/clínica · Cirugía Pediátrica"
                if effective_role_id == "professional_clinical"
                else "Actividad quirúrgica/procedimental · Cirugía Pediátrica"
            )
        _render_group(primary_title, primary_cards)
        if role_id == "professional_mixed":
            st.caption(
                "Los dos lentes conservan la misma identidad y especialidad. "
                "No se calcula ni presenta un puntaje combinado."
            )
    with tabs[1]:
        _render_secondary(secondary_cards)
        render_waitlist_analytics(dataset, current, previous, visual_context)
    with tabs[2]:
        render_origin_map(dataset, current, previous, visual_context)
    with tabs[3]:
        render_role_activity_analytics(dataset, current, previous, visual_context)
        _render_data_context(dataset)
    with tabs[4]:
        role_contract = get_role_definition(effective_role_id)
        _render_definitions(
            [*role_contract["primary_indicator_ids"], *secondary_ids]
        )
