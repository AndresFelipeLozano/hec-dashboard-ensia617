"""Role-specific KPI shell backed by the deterministic Day 3 engine."""

from __future__ import annotations

from datetime import date

import streamlit as st

from dashboard.components.common import (
    render_interpretation,
    render_kpi_cards,
    render_simulation_notice,
)
from hec_dashboard.app_config import get_ui_view
from hec_dashboard.app_state import Keys
from hec_dashboard.presentation import (
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
            help=(
                "Ambos lentes pertenecen al mismo perfil simulado y a la misma "
                "especialidad de Cirugía Pediátrica."
            ),
        )
        st.caption(
            "Mismo perfil y especialidad bajo ambos lentes: "
            f"{context['professional_short_label']} · Cirugía Pediátrica."
        )
        if lens == "clinical":
            _render_group(
                "Actividad ambulatoria/clínica · Cirugía Pediátrica",
                groups["clinical"],
            )
        else:
            _render_group(
                "Actividad quirúrgica/procedimental · Cirugía Pediátrica",
                groups["surgical"],
            )
        st.caption("No se calcula ni presenta un puntaje combinado del perfil mixto.")
    else:
        with st.spinner("Calculando indicadores…"):
            cards = build_role_presentation(
                role_id, dataset, current, previous, **kwargs
            )
        _render_group("Indicadores primarios", cards)

    st.info(
        "Próximo lote de presentación: gráficos estadísticos, mapa georreferenciado, "
        "tabla accesible del mapa y hallazgos priorizados deterministas. "
        "No se muestran valores ni alertas de reemplazo en esta etapa."
    )
