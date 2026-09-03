"""Active and candidate dataset quality summary."""

from __future__ import annotations

from collections import Counter
import csv
from functools import lru_cache
import json
from pathlib import Path

import streamlit as st

from dashboard.components.common import render_kpi_cards, render_simulation_notice
from hec_dashboard.app_state import Keys
from hec_dashboard.presentation import build_indicator_presentations
from hec_dashboard.visual_analytics import HEC_DEIS_CODE


REPO_ROOT = Path(__file__).resolve().parents[2]
WAITLIST_INDICATOR_COUNT = 10
ORIGIN_FIELDS = {
    "DERIVACIONES": "origin_establishment_code",
    "CIRUGIAS": "origin_establishment_code",
    "ACTIVIDAD_PROF": "origin_establishment_code",
    "LISTA_ESPERA_AMB": "origin_deis_code",
}


@lru_cache(maxsize=1)
def _deis_reference() -> dict[str, dict]:
    path = REPO_ROOT / "data/reference/deis_establishments_ssmc_snapshot.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["establishment_code"]: row for row in csv.DictReader(handle)}


@lru_cache(maxsize=1)
def _professional_reference() -> dict[str, dict]:
    path = REPO_ROOT / "config/professional_profiles.json"
    return {
        profile["professional_id"]: profile
        for profile in json.loads(path.read_text(encoding="utf-8"))["profiles"]
    }


@lru_cache(maxsize=1)
def _diagnosis_reference() -> dict[str, dict]:
    path = REPO_ROOT / "config/referral_diagnoses.json"
    return {
        item["diagnosis_group_id"]: item
        for item in json.loads(path.read_text(encoding="utf-8"))["diagnoses"]
    }


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


def _day5_quality_metrics(dataset, metadata: dict, summary: dict) -> dict:
    waitlist = dataset.tables.get("LISTA_ESPERA_AMB", [])
    queue_counts = Counter(row["queue_type"] for row in waitlist)
    period_counts = Counter(
        (row["period_id"], row["queue_type"]) for row in waitlist
    )

    invalid_dates = 0
    invalid_status = 0
    for row in waitlist:
        index_date = (
            row.get("queue_entry_date")
            if row.get("queue_type") == "new_consultation"
            else row.get("control_due_date")
        )
        snapshot = row.get("snapshot_date")
        completion = row.get("completion_date")
        if not index_date or not snapshot or index_date > snapshot:
            invalid_dates += 1
        if completion and (completion < index_date or completion > snapshot):
            invalid_dates += 1

        status = row.get("episode_status")
        scheduled = row.get("scheduled_date")
        exit_reason = row.get("exit_reason")
        if status == "completed" and (completion is None or exit_reason is not None):
            invalid_status += 1
        elif status == "exited" and (completion is not None or not exit_reason):
            invalid_status += 1
        elif status == "open_scheduled" and (completion is not None or scheduled is None):
            invalid_status += 1
        elif status == "open_unscheduled" and (completion is not None or scheduled is not None):
            invalid_status += 1

    reference = _deis_reference()
    referenced_codes = {
        str(row["origin_deis_code"]) for row in waitlist if row.get("origin_deis_code")
    }
    coordinate_complete = sum(
        code in reference
        and reference[code].get("coordinates_available") == "True"
        and bool(reference[code].get("latitude"))
        and bool(reference[code].get("longitude"))
        for code in referenced_codes
    )
    reference_coordinate_complete = sum(
        row.get("coordinates_available") == "True"
        and bool(row.get("latitude"))
        and bool(row.get("longitude"))
        for row in reference.values()
    )

    profiles = _professional_reference()
    assigned = [row for row in waitlist if row.get("professional_profile_id")]
    incompatible_profiles = sum(
        row["professional_profile_id"] not in profiles
        or profiles[row["professional_profile_id"]]["service_id"] != row["service_id"]
        or profiles[row["professional_profile_id"]]["specialty_id"] != row["specialty_id"]
        for row in assigned
    )
    diagnoses = _diagnosis_reference()
    diagnosis_present = any(
        row.get("referral_diagnosis_id") for row in waitlist
    )
    diagnosis_missing = sum(
        not row.get("referral_diagnosis_id") for row in waitlist
    )
    diagnosis_invalid = sum(
        row.get("referral_diagnosis_id")
        and row["referral_diagnosis_id"] not in diagnoses
        for row in waitlist
    )
    diagnosis_mismatch = sum(
        row.get("referral_diagnosis_id") in diagnoses
        and diagnoses[row["referral_diagnosis_id"]]["specialty_id"]
        != row["specialty_id"]
        for row in waitlist
    )
    internal_origin_by_sheet = {
        sheet: sum(
            str(row.get(field)) == HEC_DEIS_CODE
            for row in dataset.tables.get(sheet, [])
        )
        for sheet, field in ORIGIN_FIELDS.items()
    }
    internal_waitlist_records = internal_origin_by_sheet["LISTA_ESPERA_AMB"]

    sheet_present = "LISTA_ESPERA_AMB" in dataset.tables
    legacy_unavailable = (
        WAITLIST_INDICATOR_COUNT
        if not sheet_present and str(metadata.get("contract_version", "")).startswith("1.1")
        else 0
    )
    return {
        "sheet_present": sheet_present,
        "queue_counts": queue_counts,
        "period_counts": period_counts,
        "invalid_dates": invalid_dates + summary.get("issue_counts", {}).get("invalid_dates", 0),
        "invalid_status": invalid_status,
        "referenced_codes": len(referenced_codes),
        "coordinate_complete": coordinate_complete,
        "reference_codes": len(reference),
        "reference_coordinate_complete": reference_coordinate_complete,
        "assigned_profiles": len(assigned),
        "incompatible_profiles": incompatible_profiles,
        "legacy_unavailable": legacy_unavailable,
        "diagnosis_present": diagnosis_present,
        "diagnosis_missing": diagnosis_missing,
        "diagnosis_invalid": diagnosis_invalid,
        "diagnosis_mismatch": diagnosis_mismatch,
        "diagnosis_catalog_size": len(diagnoses),
        "internal_origin_by_sheet": internal_origin_by_sheet,
        "internal_origin_records": sum(internal_origin_by_sheet.values()),
        "internal_waitlist_records": internal_waitlist_records,
        "external_network_records": len(waitlist) - internal_waitlist_records,
    }


def _render_day5_quality(dataset, metadata: dict, summary: dict) -> None:
    metrics = _day5_quality_metrics(dataset, metadata, summary)
    st.subheader("Controles de lista de espera ambulatoria")
    st.table(
        [
            {"Control": "Hoja LISTA_ESPERA_AMB presente", "Resultado": "Sí" if metrics["sheet_present"] else "No"},
            {"Control": "Inconsistencias de cronología", "Resultado": str(metrics["invalid_dates"])},
            {"Control": "Inconsistencias de estado", "Resultado": str(metrics["invalid_status"])},
            {
                "Control": "Catálogo DEIS empaquetado con coordenadas completas",
                "Resultado": f"{metrics['reference_coordinate_complete']} de {metrics['reference_codes']}",
            },
            {
                "Control": "Orígenes DEIS con coordenadas completas",
                "Resultado": f"{metrics['coordinate_complete']} de {metrics['referenced_codes']}",
            },
            {
                "Control": "Asignaciones perfil-especialidad incompatibles",
                "Resultado": f"{metrics['incompatible_profiles']} de {metrics['assigned_profiles']}",
            },
            {
                "Control": "Indicadores no disponibles por carga legado 1.1",
                "Resultado": str(metrics["legacy_unavailable"]),
            },
            {
                "Control": "Dimensión diagnóstica simulada disponible",
                "Resultado": "Sí" if metrics["diagnosis_present"] else "No disponible (carga heredada)",
            },
            {
                "Control": "IDs diagnósticos inexistentes",
                "Resultado": str(metrics["diagnosis_invalid"]),
            },
            {
                "Control": "Diagnósticos incompatibles con especialidad",
                "Resultado": str(metrics["diagnosis_mismatch"]),
            },
            {
                "Control": "Grupos diagnósticos simulados gobernados",
                "Resultado": str(metrics["diagnosis_catalog_size"]),
            },
            {
                "Control": "Registros de origen interno (HEC) en tablas aceptadas",
                "Resultado": str(metrics["internal_origin_records"]),
            },
            *[
                {
                    "Control": f"Origen interno HEC · {sheet}",
                    "Resultado": str(count),
                }
                for sheet, count in metrics["internal_origin_by_sheet"].items()
            ],
            {
                "Control": "LISTA_ESPERA_AMB excluidos de la red externa",
                "Resultado": str(metrics["internal_waitlist_records"]),
            },
            {
                "Control": "Registros incluidos en el universo de red externa",
                "Resultado": str(metrics["external_network_records"]),
            },
        ]
    )
    st.caption(
        "Los registros con origen DEIS 111101 permanecen en los totales generales de "
        "calidad y aceptación y se desglosan por tabla. Los episodios ambulatorios se "
        "clasifican como origen interno y no participan en mapas, rankings, selectores "
        "ni exportaciones de la red externa."
    )
    st.caption(
        "En una carga 1.1 válida sin LISTA_ESPERA_AMB, los 10 indicadores de espera "
        "se informan como no disponibles; nunca como cero."
    )
    if not metrics["diagnosis_present"]:
        st.caption(
            "En cargas 1.1 o 1.2 sin referral_diagnosis_id, los controles diagnósticos "
            "se deshabilitan y su ausencia nunca se interpreta como cero."
        )
    st.table(
        [
            {
                "Tipo de cola": "Consulta nueva" if queue == "new_consultation" else "Control",
                "Episodios": count,
            }
            for queue, count in sorted(metrics["queue_counts"].items())
        ]
    )
    st.table(
        [
            {
                "Período": period,
                "Tipo de cola": "Consulta nueva" if queue == "new_consultation" else "Control",
                "Episodios": count,
            }
            for (period, queue), count in sorted(metrics["period_counts"].items())
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
    _render_day5_quality(dataset, metadata, summary)

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
