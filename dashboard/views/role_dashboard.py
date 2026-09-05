"""Role-specific Day 5 dashboard with governed visual analytics."""

from __future__ import annotations

from datetime import date

import streamlit as st

from dashboard.components.common import (
    render_badges,
    render_compact_kpi_cards,
    render_interpretation,
    render_kpi_cards,
    render_simulation_notice,
)
from dashboard.components.inpatient import render_inpatient_reference
from dashboard.components.visuals import (
    render_diabetology_activity_prototype,
    render_diabetology_origin_context,
    render_director_waitlist_prototype,
    render_origin_map,
    render_palliative_ambulatory_prototype,
    render_palliative_territorial_prototype,
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

PALLIATIVE_SERVICE_ID = "alivio_dolor_cuidados_paliativos"
DIABETOLOGY_SPECIALTY_ID = "diabetologia"


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


def _render_director_dashboard(
    dataset,
    current: tuple[date, date],
    previous: tuple[date, date],
    context: dict,
    primary_cards,
    secondary_cards,
) -> None:
    """Render the Director prototype at the visual-review gate."""

    primary_focus = [
        card
        for card in primary_cards
        if card.indicator_id not in {"referrals_total", "accepted_record_pct"}
    ]
    by_id = {card.indicator_id: card for card in primary_cards}
    tabs = st.tabs(
        [
            "Resumen ejecutivo",
            "Acceso ambulatorio",
            "Hospitalización",
            "Red territorial",
            "Métodos y calidad",
        ]
    )
    with tabs[0]:
        st.subheader("Pulso ejecutivo de acceso")
        st.caption(
            "Indicadores priorizados para reconocer acumulación y demora sin mezclar "
            "fuentes ni construir un puntaje compuesto."
        )
        render_compact_kpi_cards(primary_focus, show_interpretation=False)
        referrals = by_id.get("referrals_total")
        quality = by_id.get("accepted_record_pct")
        render_badges(
            (
                f"Calidad de carga: {quality.value_text} de registros aceptados"
                if quality and quality.is_available
                else "Calidad de carga: no disponible"
            ),
            (
                f"Contexto de demanda: {referrals.value_text} derivaciones"
                if referrals and referrals.is_available
                else "Contexto de demanda: no disponible"
            ),
            source=(
                "Datos operacionales simulados — "
                f"{current[0].strftime('%d-%m-%Y')} a {current[1].strftime('%d-%m-%Y')}"
            ),
        )
        with st.expander("Lectura y alcance de los indicadores ejecutivos"):
            render_interpretation(primary_focus)
            st.caption(
                "La calidad de carga y el volumen bruto permanecen visibles como contexto, "
                "pero no ocupan una tarjeta primaria."
            )
    with tabs[1]:
        render_director_waitlist_prototype(dataset, current, previous, context)
        with st.expander("Indicadores complementarios de acceso"):
            _render_secondary(secondary_cards)
    with tabs[2]:
        render_inpatient_reference("director")
    with tabs[3]:
        render_origin_map(dataset, current, previous, context)
    with tabs[4]:
        render_role_activity_analytics(dataset, current, previous, context)
        _render_data_context(dataset)
        role_contract = get_role_definition("director")
        with st.expander("Definiciones y denominadores operacionales"):
            _render_definitions(
                [*role_contract["primary_indicator_ids"], *secondary_indicator_ids("director")]
            )


def _render_palliative_dashboard(
    dataset,
    current: tuple[date, date],
    previous: tuple[date, date],
    context: dict,
    primary_cards,
    secondary_cards,
) -> None:
    focus_ids = {
        "wait_p75_days",
        "new_no_show_pct",
        "followup_no_show_pct",
        "discharge_rate_pct",
    }
    tabs = st.tabs(
        [
            "Resumen del servicio",
            "Comparación ambulatoria",
            "Origen territorial",
            "Datos y métodos",
        ]
    )
    with tabs[0]:
        st.subheader("Alivio del Dolor y Cuidados Paliativos")
        st.caption(
            "Vista a nivel de servicio. No se crea una especialidad artificial para "
            "habilitar filtros o visualizaciones."
        )
        render_compact_kpi_cards(
            [card for card in primary_cards if card.indicator_id in focus_ids],
            show_interpretation=False,
        )
        render_badges(
            "4 indicadores primarios",
            "Especialidad analítica: no configurada",
            source="Datos operacionales simulados — alcance de servicio",
        )
    with tabs[1]:
        render_palliative_ambulatory_prototype(
            dataset, current, previous, context
        )
    with tabs[2]:
        render_palliative_territorial_prototype(
            dataset, current, previous, context
        )
    with tabs[3]:
        with st.expander("Indicadores complementarios del servicio"):
            _render_secondary(secondary_cards)
        _render_data_context(dataset)
        role_contract = get_role_definition("service_chief_clinical")
        with st.expander("Definiciones y denominadores"):
            _render_definitions(
                [
                    *role_contract["primary_indicator_ids"],
                    *secondary_indicator_ids("service_chief_clinical"),
                ]
            )


def _render_diabetology_dashboard(
    dataset,
    current: tuple[date, date],
    previous: tuple[date, date],
    context: dict,
    primary_cards,
    secondary_cards,
) -> None:
    focus_ids = {
        "clinical_activity_completed",
        "clinical_schedule_completion_pct",
        "professional_documentation_completeness_pct",
    }
    tabs = st.tabs(
        [
            "Resumen clínico",
            "Actividad comparada",
            "Origen de la demanda",
            "Datos y métodos",
        ]
    )
    with tabs[0]:
        st.subheader("Actividad clínica · Diabetología")
        st.caption(
            "Perfil completamente simulado; las medidas no constituyen ranking, "
            "evaluación contractual ni atribución a una persona real."
        )
        render_compact_kpi_cards(
            [card for card in primary_cards if card.indicator_id in focus_ids],
            show_interpretation=False,
        )
        render_badges(
            "3 indicadores primarios",
            "Sin puntaje compuesto",
            source="ACTIVIDAD_PROF simulada — Diabetología",
        )
    with tabs[1]:
        render_diabetology_activity_prototype(
            dataset, current, previous, context
        )
    with tabs[2]:
        render_diabetology_origin_context(
            dataset, current, previous, context
        )
    with tabs[3]:
        with st.expander("Indicadores complementarios de contexto"):
            _render_secondary(secondary_cards)
        _render_data_context(dataset)
        role_contract = get_role_definition("professional_clinical")
        with st.expander("Definiciones y denominadores"):
            _render_definitions(
                [
                    *role_contract["primary_indicator_ids"],
                    *secondary_indicator_ids("professional_clinical"),
                ]
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
    if role_id == "director":
        _render_director_dashboard(
            dataset,
            current,
            previous,
            visual_context,
            primary_cards,
            secondary_cards,
        )
        return
    if (
        role_id == "service_chief_clinical"
        and context.get("service_id") == PALLIATIVE_SERVICE_ID
        and context.get("specialty_id") is None
    ):
        _render_palliative_dashboard(
            dataset,
            current,
            previous,
            visual_context,
            primary_cards,
            secondary_cards,
        )
        return
    if (
        role_id == "professional_clinical"
        and context.get("specialty_id") == DIABETOLOGY_SPECIALTY_ID
    ):
        _render_diabetology_dashboard(
            dataset,
            current,
            previous,
            visual_context,
            primary_cards,
            secondary_cards,
        )
        return
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
