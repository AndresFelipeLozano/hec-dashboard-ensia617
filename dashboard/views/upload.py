"""Session-only Excel validation and explicit activation page."""

from __future__ import annotations

import streamlit as st

from dashboard.components.common import render_simulation_notice
from hec_dashboard.app_config import REPO_ROOT
from hec_dashboard.app_state import (
    Keys,
    activate_candidate,
    restore_bundled_dataset,
    validate_candidate_bytes,
)


def _show_summary(summary: dict) -> None:
    columns = st.columns(4)
    columns[0].metric("Filas aceptadas", summary.get("accepted_rows", 0))
    columns[1].metric("Filas en cuarentena", summary.get("rejected_rows", 0))
    pct = summary.get("accepted_record_pct")
    columns[2].metric("Aceptación", "No disponible" if pct is None else f"{pct:.1f}%")
    columns[3].metric("Errores estructurales", summary.get("structural_error_count", 0))
    per_sheet = summary.get("per_sheet", {})
    if per_sheet:
        st.table(
            [
                {
                    "Hoja": name,
                    "Aceptadas": values["accepted"],
                    "Cuarentena": values["quarantined"],
                }
                for name, values in per_sheet.items()
            ]
        )
    reasons = summary.get("rejection_reasons", {})
    if reasons:
        st.write("**Motivos agregados de rechazo o advertencia**")
        st.table(
            [
                {"Código": code, "Cantidad": count}
                for code, count in sorted(reasons.items())
            ]
        )


def render() -> None:
    st.header("Carga y validación de datos")
    render_simulation_notice()
    st.warning(
        "Solo se admiten libros XLSX con datos completamente simulados. El archivo "
        "permanece en la sesión y nunca reemplaza automáticamente el dataset activo."
    )
    template = REPO_ROOT / "templates" / "plantilla_carga_hec_v1.xlsx"
    st.download_button(
        "Descargar plantilla XLSX aprobada",
        data=template.read_bytes(),
        file_name=template.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    uploaded = st.file_uploader(
        "Seleccionar candidato XLSX (máximo 20 MB)",
        type=["xlsx"],
        accept_multiple_files=False,
    )
    if uploaded is not None:
        st.write(f"**Candidato:** {uploaded.name}")
        if st.button("Validar candidato", type="primary"):
            try:
                report = validate_candidate_bytes(
                    st.session_state, uploaded.name, uploaded.getvalue()
                )
                if report.activatable:
                    st.success(
                        "Candidato válido. La activación sigue pendiente y es explícita."
                    )
                else:
                    st.error(
                        "Candidato rechazado. El dataset activo anterior se conservó."
                    )
            except ValueError:
                st.error(
                    "El candidato no pudo validarse de forma segura. "
                    "El dataset activo anterior se conservó."
                )

    summary = st.session_state.get(Keys.CANDIDATE_VALIDATION_SUMMARY)
    if summary:
        st.subheader("Resultado del último candidato")
        metadata = (
            st.session_state[Keys.CANDIDATE_DATASET].metadata
            if st.session_state.get(Keys.CANDIDATE_DATASET) is not None
            else {}
        )
        st.write(f"**Archivo:** {st.session_state.get(Keys.CANDIDATE_FILE_NAME)}")
        st.write(f"**Contrato:** {metadata.get('contract_version', 'No disponible')}")
        st.write(f"**Dataset:** {metadata.get('dataset_id', 'No disponible')}")
        _show_summary(summary)
        if summary.get("activatable") and st.button("Activar candidato validado"):
            activate_candidate(st.session_state)
            st.success("Candidato activado atómicamente para esta sesión.")
            st.rerun()

    st.divider()
    if st.button("Restaurar dataset simulado incluido"):
        restore_bundled_dataset(st.session_state)
        st.success("Dataset simulado incluido restaurado y validado.")
        st.rerun()
    active = st.session_state.get(Keys.ACTIVE_DATASET_METADATA) or {}
    st.caption(
        f"Dataset activo: {active.get('dataset_id', 'No disponible')} · "
        f"{st.session_state.get(Keys.ACTIVE_SOURCE_MODE, 'No disponible')}"
    )
