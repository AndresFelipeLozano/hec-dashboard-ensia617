"""Governed, role-aware aggregates for the Day 5 visual layer."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import date
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from typing import Any, Iterable

from .app_config import (
    REPO_ROOT,
    get_role_definition,
    referral_diagnoses,
    specialty_label,
)
from .data_ingestion import CandidateDataset
from .indicator_engine import IndicatorContext, IndicatorEngine, _percentile


OPEN_STATUSES = {"open_unscheduled", "open_scheduled"}
HEC_DEIS_CODE = "111101"
HEC_MARKER_SIZE = 18
HEC_MARKER_SYMBOL = "hospital"
AGING_BANDS = (
    ("0–30 días", 0, 30),
    ("31–60 días", 31, 60),
    ("61–90 días", 61, 90),
    (">90 días", 91, None),
)
WAITLIST_TREND_IDS = (
    "new_waitlist_open_count",
    "new_wait_p75_days",
    "followup_overdue_open_count",
    "followup_overdue_p75_days",
)


def _scope_operational_rows(
    dataset: CandidateDataset,
    sheet: str,
    period: tuple[date, date],
    role_context: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = dataset.tables.get(sheet, [])
    service_id = role_context.get("service_id")
    specialty_id = role_context.get("specialty_id")
    profile_id = role_context.get("simulated_profile_key")
    lens = role_context.get("professional_lens")
    result = []
    for row in rows:
        if not period[0] <= row["period_date"] <= period[1]:
            continue
        if service_id and row.get("service_id") != service_id:
            continue
        if specialty_id and row.get("specialty_id") != specialty_id:
            continue
        if sheet == "ACTIVIDAD_PROF" and profile_id:
            if row.get("simulated_profile_key") != profile_id:
                continue
            if lens and row.get("lens") != lens:
                continue
        result.append(row)
    return result


def waitlist_indicator_trend(
    dataset: CandidateDataset,
    current_period: tuple[date, date],
    previous_period: tuple[date, date],
    role_context: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, Any]]:
    """Return two-period values calculated exclusively by the indicator engine."""

    role_id = role_context["role_id"]
    role = get_role_definition(role_id, repo_root)
    engine = IndicatorEngine.from_repo(repo_root)
    output = []
    periods = (("Comparación", previous_period, current_period), ("Actual", current_period, previous_period))
    for period_label, period, comparison in periods:
        context = IndicatorContext(
            period_start=period[0],
            period_end=period[1],
            previous_period_start=comparison[0],
            previous_period_end=comparison[1],
            indicator_profile=role["indicator_profile"],
            service_id=role_context.get("service_id"),
            specialty_id=role_context.get("specialty_id"),
            simulated_profile_key=role_context.get("simulated_profile_key"),
            professional_lens=role_context.get("professional_lens"),
        )
        for indicator_id in WAITLIST_TREND_IDS:
            result = engine.calculate(indicator_id, dataset, context)
            output.append(
                {
                    "Período": period_label,
                    "Indicador": result.display_name_es,
                    "Valor": result.value,
                    "Unidad": "Episodios" if result.unit == "count" else "Días",
                    "Estado": result.status,
                }
            )
    return output


def role_activity_trend(
    dataset: CandidateDataset,
    current_period: tuple[date, date],
    previous_period: tuple[date, date],
    role_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build role-authorized operational counts without event-level disclosure."""

    role_id = role_context["role_id"]
    output: list[dict[str, Any]] = []
    for period_label, period in (("Comparación", previous_period), ("Actual", current_period)):
        if role_id in {"director", "medical_director"}:
            referrals = _scope_operational_rows(dataset, "DERIVACIONES", period, role_context)
            surgeries = _scope_operational_rows(dataset, "CIRUGIAS", period, role_context)
            series = {
                "Demanda ambulatoria derivada": len(referrals),
                "Demanda quirúrgica registrada": len(surgeries),
            }
        elif role_id == "service_chief_clinical":
            rows = _scope_operational_rows(dataset, "DERIVACIONES", period, role_context)
            series = {
                "Derivaciones nuevas": sum(row["referral_type"] == "new" for row in rows),
                "Derivaciones de control": sum(row["referral_type"] == "followup" for row in rows),
                "Inasistencias nuevas": sum(row["referral_type"] == "new" and row["no_show_flag"] for row in rows),
                "Inasistencias de control": sum(row["referral_type"] == "followup" and row["no_show_flag"] for row in rows),
            }
        elif role_id == "service_chief_surgical":
            rows = _scope_operational_rows(dataset, "CIRUGIAS", period, role_context)
            labels = {"waitlisted": "En espera", "completed": "Completadas", "suspended": "Suspendidas"}
            series = {label: sum(row["status"] == status for row in rows) for status, label in labels.items()}
        else:
            rows = _scope_operational_rows(dataset, "ACTIVIDAD_PROF", period, role_context)
            series = {
                "Programada": sum(row["scheduled_flag"] for row in rows),
                "Completada": sum(row["completed_flag"] for row in rows),
            }
            if role_id == "professional_clinical":
                series["Inasistencia"] = sum(row["no_show_flag"] for row in rows)
            else:
                series["Suspendida"] = sum(row["suspended_flag"] for row in rows)
        output.extend(
            {"Período": period_label, "Serie": label, "Eventos": value}
            for label, value in series.items()
        )
    return output


def role_activity_composition(
    dataset: CandidateDataset,
    period: tuple[date, date],
    role_context: dict[str, Any],
) -> list[dict[str, Any]]:
    role_id = role_context["role_id"]
    if role_id in {"director", "medical_director"}:
        rows = _scope_operational_rows(dataset, "DERIVACIONES", period, role_context)
        counts = Counter(row["specialty_id"] for row in rows)
        title = "Especialidad"
    elif role_id == "service_chief_clinical":
        rows = _scope_operational_rows(dataset, "DERIVACIONES", period, role_context)
        status_labels = {"waiting": "En espera", "completed": "Completada", "discharged": "Alta", "teleconsult": "Teleconsulta"}
        counts = Counter(status_labels[row["status"]] for row in rows)
        title = "Resultado ambulatorio"
    elif role_id == "service_chief_surgical":
        rows = _scope_operational_rows(dataset, "CIRUGIAS", period, role_context)
        procedure_labels = {"PROC-CIR": "Cirugía", "PROC-CMA": "Cirugía mayor ambulatoria", "PROC-ORL": "Otorrinolaringología", "PROC-TRA": "Traumatología", "PROC-URO": "Urología"}
        counts = Counter(procedure_labels[row["procedure_code"]] for row in rows)
        title = "Procedimiento"
    else:
        rows = _scope_operational_rows(dataset, "ACTIVIDAD_PROF", period, role_context)
        activity_labels = {"CONS-NUEVA": "Consulta nueva", "CONS-CONTROL": "Control", "TELECONS": "Teleconsulta", "PROC-CIR": "Procedimiento quirúrgico", "PROC-CMA": "Cirugía mayor ambulatoria", "PROC-TRA": "Procedimiento traumatológico"}
        counts = Counter(activity_labels[row["activity_code"]] for row in rows)
        title = "Tipo de actividad"
    return [
        {title: label, "Eventos": count}
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def scoped_waitlist_rows(
    dataset: CandidateDataset,
    period: tuple[date, date],
    role_context: dict[str, Any],
    *,
    queue_type: str | None = None,
) -> list[dict[str, Any]]:
    """Apply the same approved service, specialty and professional semantics."""

    rows = dataset.tables.get("LISTA_ESPERA_AMB", [])
    service_id = role_context.get("service_id")
    specialty_id = role_context.get("specialty_id")
    profile_id = role_context.get("simulated_profile_key")
    prestation_type = role_context.get("prestation_type")
    referral_diagnosis_id = role_context.get("referral_diagnosis_id")
    professional_scope = str(role_context.get("role_id", "")).startswith(
        "professional_"
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        if not period[0] <= row["snapshot_date"] <= period[1]:
            continue
        if service_id and row["service_id"] != service_id:
            continue
        if specialty_id and row["specialty_id"] != specialty_id:
            continue
        if queue_type and row["queue_type"] != queue_type:
            continue
        if prestation_type and row["requested_prestation"] != prestation_type:
            continue
        if (
            referral_diagnosis_id
            and row.get("referral_diagnosis_id") != referral_diagnosis_id
        ):
            continue
        if (
            professional_scope
            and row["queue_type"] == "followup_control"
            and profile_id
            and row.get("professional_profile_id") != profile_id
        ):
            continue
        result.append(row)
    return result


def scoped_network_rows(
    dataset: CandidateDataset,
    period: tuple[date, date],
    role_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return external-origin rows without implying professional attribution.

    Hospital El Carmen is the destination/reference institution. Its rows remain in
    the accepted dataset and in general quality totals, but are not part of the
    external referral-network map, rankings, selectors, tables or exports.
    """

    context = dict(role_context)
    if str(context.get("role_id", "")).startswith("professional_"):
        context["simulated_profile_key"] = None
    return [
        row
        for row in scoped_waitlist_rows(dataset, period, context)
        if str(row.get("origin_deis_code")) != HEC_DEIS_CODE
    ]


def _age_days(row: dict[str, Any]) -> int:
    index_date = (
        row["queue_entry_date"]
        if row["queue_type"] == "new_consultation"
        else row["control_due_date"]
    )
    return (row["snapshot_date"] - index_date).days


def aging_distribution(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        if row["episode_status"] not in OPEN_STATUSES:
            continue
        age = _age_days(row)
        label = next(
            name
            for name, lower, upper in AGING_BANDS
            if age >= lower and (upper is None or age <= upper)
        )
        queue = (
            "Consulta nueva"
            if row["queue_type"] == "new_consultation"
            else "Control vencido"
        )
        counts[(queue, label)] += 1
    return [
        {"Cola": queue, "Tramo de antigüedad": band, "Episodios": counts[(queue, band)]}
        for queue in ("Consulta nueva", "Control vencido")
        for band, _, _ in AGING_BANDS
    ]


def status_flow(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {
        "open_unscheduled": "Abierto sin programación",
        "open_scheduled": "Abierto programado",
        "completed": "Completado",
        "exited": "Egreso válido",
    }
    counts: Counter[tuple[str, str]] = Counter(
        (row["queue_type"], row["episode_status"]) for row in rows
    )
    return [
        {
            "Cola": "Consulta nueva" if queue == "new_consultation" else "Control",
            "Estado": labels[status],
            "Episodios": counts[(queue, status)],
        }
        for queue in ("new_consultation", "followup_control")
        for status in labels
    ]


def prestation_composition(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(row["requested_prestation"] for row in rows)
    return [
        {"Prestación solicitada": key, "Episodios": value}
        for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def specialty_pressure(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["service_id"], row["specialty_id"])].append(row)
    result = []
    for (service_id, specialty_id), values in sorted(groups.items()):
        open_rows = [row for row in values if row["episode_status"] in OPEN_STATUSES]
        ages = [float(_age_days(row)) for row in open_rows]
        result.append(
            {
                "Servicio": service_id,
                "Especialidad": specialty_id,
                "Abiertos": len(open_rows),
                "P75 días": round(_percentile(ages, 0.75), 1) if ages else None,
                ">90 días": sum(value > 90 for value in ages),
            }
        )
    return sorted(result, key=lambda row: (-row[">90 días"], -row["Abiertos"], row["Especialidad"]))


def _reference_by_code(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = repo_root / "data" / "reference" / "deis_establishments_ssmc_snapshot.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["establishment_code"]: row for row in csv.DictReader(handle)}


def _ranked_counts(values: Iterable[str]) -> list[tuple[str, int]]:
    return sorted(Counter(values).items(), key=lambda item: (-item[1], item[0]))


def _diagnosis_by_id(repo_root: Path) -> dict[str, dict[str, Any]]:
    return {
        item["diagnosis_group_id"]: item
        for item in referral_diagnoses(repo_root=repo_root)
    }


def diagnosis_options(
    rows: Iterable[dict[str, Any]], *, repo_root: Path = REPO_ROOT
) -> list[dict[str, str]]:
    """Return only governed diagnoses actually represented in a scoped dataset."""

    represented = {
        row.get("referral_diagnosis_id")
        for row in rows
        if row.get("referral_diagnosis_id")
    }
    catalog = _diagnosis_by_id(repo_root)
    return [
        {
            "diagnosis_group_id": diagnosis_id,
            "label_es": catalog[diagnosis_id]["label_es"],
        }
        for diagnosis_id in sorted(
            represented,
            key=lambda value: catalog.get(value, {}).get("label_es", value).casefold(),
        )
        if diagnosis_id in catalog
    ]


def map_cache_key(
    dataset: CandidateDataset,
    current_period: tuple[date, date],
    previous_period: tuple[date, date],
    role_context: dict[str, Any],
) -> tuple[Any, ...]:
    """Complete immutable key for any future map-level caching."""

    return (
        dataset.metadata.get("dataset_id"),
        dataset.metadata.get("contract_version"),
        current_period,
        previous_period,
        role_context.get("role_id"),
        role_context.get("service_id"),
        role_context.get("specialty_id"),
        role_context.get("simulated_profile_key"),
        role_context.get("professional_lens"),
        role_context.get("prestation_type"),
        role_context.get("referral_diagnosis_id"),
        role_context.get("selected_center_code"),
        role_context.get("map_mode"),
        role_context.get("color_mode"),
    )


def origin_bubbles(
    dataset: CandidateDataset,
    current_period: tuple[date, date],
    previous_period: tuple[date, date],
    role_context: dict[str, Any],
    *,
    minimum_cell_n: int = 10,
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, Any]]:
    current = scoped_network_rows(dataset, current_period, role_context)
    previous = scoped_network_rows(dataset, previous_period, role_context)
    current_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    previous_counts: Counter[str] = Counter()
    for row in current:
        current_groups[row["origin_deis_code"]].append(row)
    for row in previous:
        previous_counts[row["origin_deis_code"]] += 1
    reference = _reference_by_code(repo_root)
    diagnosis_catalog = _diagnosis_by_id(repo_root)
    filtered_total = len(current)
    specialty_context = (
        specialty_label(role_context["specialty_id"], repo_root)
        if role_context.get("specialty_id")
        else "Todas las especialidades"
    )
    prestation_labels = {
        "consulta_nueva": "Consulta nueva",
        "control_especialidad": "Control de especialidad",
        "evaluacion_preoperatoria": "Evaluación preoperatoria",
        "procedimiento_ambulatorio": "Procedimiento ambulatorio",
    }
    output = []
    denominator_context = dict(role_context)
    if role_context.get("role_id") in {"director", "medical_director"}:
        denominator_context["service_id"] = None
        denominator_context["specialty_id"] = None
    denominator_context["referral_diagnosis_id"] = None
    all_center_counts = Counter(
        row["origin_deis_code"]
        for row in scoped_network_rows(dataset, current_period, denominator_context)
    )
    for code, rows in sorted(current_groups.items()):
        if len(rows) < minimum_cell_n:
            continue
        establishment = reference.get(code)
        if not establishment or establishment.get("coordinates_available", "").casefold() != "true":
            continue
        prior = previous_counts[code]
        prestation_counts = Counter(row["requested_prestation"] for row in rows)
        main_prestation = sorted(
            prestation_counts.items(), key=lambda item: (-item[1], item[0])
        )[0][0]
        open_rows = [row for row in rows if row["episode_status"] in OPEN_STATUSES]
        ranked_specialties = _ranked_counts(row["specialty_id"] for row in rows)
        dominant_specialty_id = ranked_specialties[0][0]
        ranked_diagnoses = _ranked_counts(
            row["referral_diagnosis_id"]
            for row in rows
            if row.get("referral_diagnosis_id")
        )
        dominant_diagnosis = (
            diagnosis_catalog[ranked_diagnoses[0][0]]["label_es"]
            if ranked_diagnoses and ranked_diagnoses[0][0] in diagnosis_catalog
            else "No disponible en carga heredada"
        )
        delta = len(rows) - prior
        trend_label = "Aumento" if delta > 0 else "Disminución" if delta < 0 else "Estable"
        center_total = all_center_counts.get(code, 0)
        output.append(
            {
                "Código DEIS": code,
                "Establecimiento": establishment["establishment_name"],
                "Comuna": establishment["commune_name"],
                "Latitud": float(establishment["latitude"]),
                "Longitud": float(establishment["longitude"]),
                "Episodios": len(rows),
                "Participación (%)": round(len(rows) * 100 / filtered_total, 2),
                "Abiertos": len(open_rows),
                "Variación": len(rows) - prior,
                "Tendencia": trend_label,
                "Prestación principal": prestation_labels[main_prestation],
                "Especialidad seleccionada": specialty_context,
                "Especialidad predominante": specialty_label(
                    dominant_specialty_id, repo_root
                ),
                "Top tres especialidades": " · ".join(
                    f"{specialty_label(specialty_id, repo_root)} ({count})"
                    for specialty_id, count in ranked_specialties[:3]
                ),
                "Diagnóstico predominante": dominant_diagnosis,
                "Participación de especialidad en centro (%)": (
                    round(len(rows) * 100 / center_total, 2)
                    if center_total
                    else None
                ),
                "Período actual": (
                    f"{current_period[0].isoformat()} a {current_period[1].isoformat()}"
                ),
                "Período comparación": (
                    f"{previous_period[0].isoformat()} a {previous_period[1].isoformat()}"
                ),
            }
        )
    return sorted(output, key=lambda row: (-row["Episodios"], row["Código DEIS"]))


def map_signature(
    rows: list[dict[str, Any]],
    dataset: CandidateDataset,
    current_period: tuple[date, date],
    previous_period: tuple[date, date],
    role_context: dict[str, Any],
) -> str:
    """Hash complete context and aggregate rows to detect ignored filters."""

    payload = {
        "cache_key": [str(value) for value in map_cache_key(
            dataset, current_period, previous_period, role_context
        )],
        "rows": [
            {
                key: row.get(key)
                for key in (
                    "Código DEIS",
                    "Episodios",
                    "Variación",
                    "Tendencia",
                    "Especialidad predominante",
                    "Diagnóstico predominante",
                    "Prestación principal",
                )
            }
            for row in rows
        ],
    }
    return sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def referring_center_specialties(
    dataset: CandidateDataset,
    current_period: tuple[date, date],
    previous_period: tuple[date, date],
    role_context: dict[str, Any],
    center_code: str,
    *,
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, Any]]:
    if str(center_code) == HEC_DEIS_CODE:
        return []
    context = dict(role_context)
    if context.get("role_id") in {"director", "medical_director"}:
        context["service_id"] = None
        context["specialty_id"] = None
    context["referral_diagnosis_id"] = None
    current = [
        row
        for row in scoped_network_rows(dataset, current_period, context)
        if row["origin_deis_code"] == center_code
    ]
    previous = [
        row
        for row in scoped_network_rows(dataset, previous_period, context)
        if row["origin_deis_code"] == center_code
    ]
    current_counts = Counter(row["specialty_id"] for row in current)
    previous_counts = Counter(row["specialty_id"] for row in previous)
    total = len(current)
    return [
        {
            "Especialidad": specialty_label(specialty_id, repo_root),
            "Especialidad ID": specialty_id,
            "Actual": count,
            "Comparación": previous_counts[specialty_id],
            "Variación": count - previous_counts[specialty_id],
            "Participación del centro (%)": round(count * 100 / total, 2),
        }
        for specialty_id, count in sorted(
            current_counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]


def referring_center_diagnoses(
    dataset: CandidateDataset,
    period: tuple[date, date],
    role_context: dict[str, Any],
    center_code: str,
    *,
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, Any]]:
    if str(center_code) == HEC_DEIS_CODE:
        return []
    context = dict(role_context)
    context["referral_diagnosis_id"] = None
    rows = [
        row
        for row in scoped_network_rows(dataset, period, context)
        if row["origin_deis_code"] == center_code
        and row.get("referral_diagnosis_id")
    ]
    catalog = _diagnosis_by_id(repo_root)
    counts = Counter(row["referral_diagnosis_id"] for row in rows)
    return [
        {
            "Diagnóstico o motivo de derivación simulado": catalog[diagnosis_id]["label_es"],
            "Diagnóstico ID": diagnosis_id,
            "Episodios": count,
            "Participación del centro-especialidad (%)": round(
                count * 100 / len(rows), 2
            ),
        }
        for diagnosis_id, count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
        if diagnosis_id in catalog
    ]


def diagnosis_composition_by_establishment(
    dataset: CandidateDataset,
    period: tuple[date, date],
    role_context: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, Any]]:
    context = dict(role_context)
    context["referral_diagnosis_id"] = None
    rows = scoped_network_rows(dataset, period, context)
    reference = _reference_by_code(repo_root)
    catalog = _diagnosis_by_id(repo_root)
    counts = Counter(
        (row["origin_deis_code"], row["referral_diagnosis_id"])
        for row in rows
        if row.get("referral_diagnosis_id")
    )
    return [
        {
            "Establecimiento": reference[code]["establishment_name"],
            "Código DEIS": code,
            "Diagnóstico o motivo de derivación simulado": catalog[diagnosis_id]["label_es"],
            "Episodios": count,
        }
        for (code, diagnosis_id), count in sorted(
            counts.items(), key=lambda item: (item[0][0], -item[1], item[0][1])
        )
        if code in reference and diagnosis_id in catalog
    ]


def referring_center_prestations(
    dataset: CandidateDataset,
    period: tuple[date, date],
    role_context: dict[str, Any],
    center_code: str,
) -> list[dict[str, Any]]:
    if str(center_code) == HEC_DEIS_CODE:
        return []
    context = dict(role_context)
    context["prestation_type"] = None
    rows = [
        row
        for row in scoped_network_rows(dataset, period, context)
        if row["origin_deis_code"] == center_code
    ]
    labels = {
        "consulta_nueva": "Consulta nueva",
        "control_especialidad": "Control de especialidad",
        "evaluacion_preoperatoria": "Evaluación preoperatoria",
        "procedimiento_ambulatorio": "Procedimiento ambulatorio",
    }
    return [
        {"Prestación solicitada": labels[value], "Episodios": count}
        for value, count in _ranked_counts(
            row["requested_prestation"] for row in rows
        )
    ]


def center_waitlist_context(
    dataset: CandidateDataset,
    period: tuple[date, date],
    role_context: dict[str, Any],
    center_code: str,
) -> list[dict[str, Any]]:
    if str(center_code) == HEC_DEIS_CODE:
        return []
    context = dict(role_context)
    context["referral_diagnosis_id"] = None
    rows = [
        row
        for row in scoped_network_rows(dataset, period, context)
        if row["origin_deis_code"] == center_code
    ]
    return [
        {
            "Cola": "Consulta nueva" if queue == "new_consultation" else "Control",
            "Total": sum(row["queue_type"] == queue for row in rows),
            "Abiertos": sum(
                row["queue_type"] == queue
                and row["episode_status"] in OPEN_STATUSES
                for row in rows
            ),
        }
        for queue in ("new_consultation", "followup_control")
    ]


def hec_marker(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    establishment = _reference_by_code(repo_root)[HEC_DEIS_CODE]
    return {
        "Código DEIS": HEC_DEIS_CODE,
        "Establecimiento": establishment["establishment_name"],
        "Latitud": float(establishment["latitude"]),
        "Longitud": float(establishment["longitude"]),
    }


def prioritized_findings(rows: Iterable[dict[str, Any]], limit: int = 5) -> list[dict[str, str]]:
    pressure = specialty_pressure(rows)
    findings = []
    for item in pressure[:limit]:
        findings.append(
            {
                "Hallazgo": (
                    f"{item['Especialidad']}: {item['>90 días']} episodios abiertos "
                    f"superan 90 días; P75 {item['P75 días']} días."
                ),
                "Límite interpretativo": (
                    "Señal descriptiva sobre datos simulados; no demuestra causa ni desempeño individual."
                ),
                "Acción de revisión": (
                    "Revisar priorización, capacidad, programación y calidad del registro agregado."
                ),
            }
        )
    return findings


def rows_to_csv(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")
