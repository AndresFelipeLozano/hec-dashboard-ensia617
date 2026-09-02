"""Active and candidate dataset quality summary."""

from __future__ import annotations

import streamlit as st

from dashboard.components.common import render_kpi_cards, render_simulation_notice
from hec_dashboard.app_state import Keys
from hec_dashboard.presentation import build_indicator_presentations


def _quality_table(summary: dict) -> None:
    per_sheet = summary.get("per_sheet", {})
    if per_sheet:
        st.table(
            [
                {
                    "Hoja": sheet,
                    "Aceptadas": values["accepted"],
                    "Cuarentena": values["quarantined"],
                }
                for sheet, values in per_sheet.items()
            ]
        )
    issue_counts = summary.get("issue_counts", {})
    labels = {
        "missing_critical_fields": "Campos críticos faltantes o inválidos",
        "invalid_codes": "Códigos inválidos",
        "invalid_dates": "Fechas inválidas/fuera del período",
        "duplicate_identifiers": "Identificadores duplicados",
        "unmatched_deis_origin_codes": "Orígenes DEIS sin correspondencia",
    }
    st.table(
        [
            {"Control": labels[key], "Cantidad": issue_counts.get(key, 0)}
            for key in labels
        ]
    )


def render() -> None:
    st.header("Calidad y estado del conjunto de datos")
    render_simulation_notice()
    dataset = st.session_state.get(Keys.ACTIVE_DATASET)
    if dataset is None:
        st.warning("No hay un dataset activo validado.")
        return
    metadata = st.session_state.get(Keys.ACTIVE_DATASET_METADATA) or {}
    summary = st.session_state.get(Keys.ACTIVE_VALIDATION_SUMMARY) or {}
    st.write(f"**Dataset activo:** {metadata.get('dataset_id', 'No disponible')}")
    st.write(f"**Contrato:** {metadata.get('contract_version', 'No disponible')}")
    st.write(f"**Modo de fuente:** {st.session_state.get(Keys.ACTIVE_SOURCE_MODE)}")
    st.write("**Simulación:** Sí, datos operacionales y perfiles completamente simulados")
    st.write(
        f"**Activación de sesión:** {st.session_state.get(Keys.LAST_ACTIVATION_TIMESTAMP)}"
    )
    st.write(
        f"**Cobertura declarada:** {metadata.get('period_start')} a "
        f"{metadata.get('period_end')}"
    )
    columns = st.columns(3)
    columns[0].metric("Aceptadas", summary.get("accepted_rows", 0))
    columns[1].metric("Cuarentena", summary.get("rejected_rows", 0))
    pct = summary.get("accepted_record_pct")
    columns[2].metric("Aceptación", "No disponible" if pct is None else f"{pct:.1f}%")
    _quality_table(summary)

    cards = build_indicator_presentations(
        ["accepted_record_pct", "critical_field_completeness_pct"],
        "director",
        dataset,
        st.session_state[Keys.SELECTED_CURRENT_PERIOD],
        st.session_state[Keys.SELECTED_PREVIOUS_PERIOD],
    )
    st.subheader("Indicadores de calidad aprobados")
    render_kpi_cards(cards)

    candidate = st.session_state.get(Keys.CANDIDATE_VALIDATION_SUMMARY)
    if candidate:
        st.subheader("Resultado del último candidato")
        if candidate.get("activatable"):
            st.info(
                "El candidato fue validado; solo reemplaza al activo tras activación explícita."
            )
        else:
            st.warning("El candidato fue rechazado y no reemplazó el dataset activo.")
        _quality_table(candidate)
