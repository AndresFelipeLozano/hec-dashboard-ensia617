"""Shared, accessible Streamlit frame and KPI rendering."""

from __future__ import annotations

from datetime import date
from typing import Any, MutableMapping

import streamlit as st

from hec_dashboard.app_config import role_label, service_label, specialty_label
from hec_dashboard.app_state import Keys, reset_role
from hec_dashboard.presentation import KpiPresentation


FOOTER_TEXT = "Desarrollo propuesto en la asignatura Tecnología de la Información, Magíster en Administración de Salud, FEN."


def render_footer() -> None:
    """Render the shared, in-flow academic footer with static safe content."""

    st.markdown(
        """
        <style>
        .hec-global-footer {
            margin-top: 3rem;
            padding: 1.25rem 0.75rem 0.75rem;
            border-top: 1px solid #D0D5DD;
            color: #667085;
            font-size: 0.8rem;
            line-height: 1.5;
            text-align: center;
            overflow-wrap: anywhere;
        }
        @media (max-width: 390px) {
            .hec-global-footer {
                margin-top: 2rem;
                padding-left: 0.25rem;
                padding-right: 0.25rem;
                font-size: 0.76rem;
            }
        }
        </style>
        <footer class="hec-global-footer" role="contentinfo">
            Desarrollo propuesto en la asignatura Tecnología de la Información, Magíster en Administración de Salud, FEN.
        </footer>
        """,
        unsafe_allow_html=True,
    )


def _period_text(value: tuple[date, date] | None) -> str:
    if not value:
        return "No disponible"
    return f"{value[0].strftime('%d-%m-%Y')} a {value[1].strftime('%d-%m-%Y')}"


def render_app_frame(state: MutableMapping[str, Any]) -> None:
    st.title("HEC | Apoyo a decisiones por rol")
    st.caption(
        "Demostración académica ENSIA617 · Datos completamente simulados · "
        "No corresponde a autenticación ni a un sistema institucional productivo."
    )
    metadata = state.get(Keys.ACTIVE_DATASET_METADATA) or {}
    context = state.get(Keys.ROLE_CONTEXT) or {}
    with st.sidebar:
        st.subheader("Contexto actual")
        st.write(f"**Rol:** {role_label(context.get('role_id'))}")
        is_professional = str(context.get("role_id", "")).startswith("professional_")
        if context.get("service_id") and not is_professional:
            st.caption(f"Unidad: {service_label(context['service_id'])}")
        if context.get("specialty_id"):
            specialty_context = context.get(
                "specialty_context_label",
                specialty_label(context["specialty_id"]),
            )
            st.caption(f"Especialidad: {specialty_context}")
        if context.get("simulated_profile_key"):
            st.caption(f"Perfil: {context['professional_short_label']}")
        if context.get("professional_lens"):
            lens_label = (
                "Clínico"
                if context["professional_lens"] == "clinical"
                else "Quirúrgico"
            )
            st.caption(f"Lente: {lens_label}")
        elif context.get("professional_lenses"):
            st.caption("Lentes separados: Clínico y Quirúrgico")
            st.caption(
                "Actividad por lente: ambulatoria/clínica · "
                "quirúrgica/procedimental"
            )
        st.write(f"**Dataset activo:** {metadata.get('dataset_id', 'No disponible')}")
        st.write(f"**Período:** {_period_text(state.get(Keys.SELECTED_CURRENT_PERIOD))}")
        st.write(f"**Comparación:** {_period_text(state.get(Keys.SELECTED_PREVIOUS_PERIOD))}")
        st.caption("Dataset validado, simulado y conservado solo durante esta sesión.")
        if context and st.button("Cambiar o restablecer rol", use_container_width=True):
            reset_role(state)
            st.rerun()


def render_simulation_notice() -> None:
    st.caption(
        "**Datos completamente simulados.** No contienen identificadores reales, "
        "direcciones de pacientes ni detalle a nivel de paciente."
    )


def render_kpi_cards(cards: list[KpiPresentation]) -> None:
    available = [card for card in cards if card.is_available]
    if not available:
        st.caption("No hay KPI calculables para los filtros seleccionados.")
        return
    for offset in range(0, len(available), 3):
        row = available[offset : offset + 3]
        columns = st.columns(len(row))
        for column, card in zip(columns, row):
            with column:
                st.metric(
                    card.label_es,
                    card.value_text,
                    delta=card.delta_text,
                    help=card.explanation_es,
                )
                st.caption(
                    f"Estado: {card.status_label_es}. "
                    f"n válido: {card.valid_n}. {card.explanation_es}"
                )


def render_interpretation(cards: list[KpiPresentation]) -> None:
    unavailable = [card for card in cards if not card.is_available]
    if unavailable:
        st.markdown("#### Disponibilidad de indicadores")
        st.caption(
            f"{len(unavailable)} indicador(es) requieren contexto adicional o no "
            "pueden calcularse con los filtros actuales."
        )
        st.dataframe(
            [
                {
                    "Indicador": card.label_es,
                    "Estado": card.status_label_es,
                    "n válido": card.valid_n,
                    "n mínimo": card.minimum_valid_n,
                }
                for card in unavailable
            ],
            hide_index=True,
            width="stretch",
        )
        with st.expander("Ver razones de disponibilidad"):
            for card in unavailable:
                st.markdown(f"**{card.label_es}:** {card.explanation_es}")
    references = [card.target_text for card in cards if card.target_text]
    st.subheader("Referencias y alcance")
    if references:
        for reference in dict.fromkeys(references):
            st.write(f"- {reference}")
    else:
        st.caption("No hay una meta de desempeño aplicable para estas tarjetas.")
    st.caption(
        "Las referencias ministeriales con aplicabilidad pendiente no se presentan "
        "como metas oficiales del Hospital El Carmen."
    )
