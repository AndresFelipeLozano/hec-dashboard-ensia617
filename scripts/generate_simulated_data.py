#!/usr/bin/env python3
"""Generate deterministic, coverage-oriented, identifier-free simulated data."""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from hashlib import sha256
from html import escape
from io import StringIO
import json
import random
import re
from pathlib import Path
import tempfile
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "simulated"
DEFAULT_WORKBOOK_SOURCE = REPO_ROOT / "templates" / "plantilla_carga_hec_v1.xlsx"
DEFAULT_WORKBOOK_OUTPUT = REPO_ROOT / "templates" / "plantilla_carga_hec_1_3.xlsx"
SEED = 617
DATASET_ID = "hec-sim-day5-v1"
DATASET_NAME = (
    "Demostración HEC — Día 5 red de derivación y lista de espera ambulatoria"
)
GENERATED_AT_UTC = "2026-09-02T12:00:00Z"
HEC_DEIS_CODE = "111101"
PERIOD_MONTHS = {
    "Q1": ("2026-01-01", "2026-02-01", "2026-03-01"),
    "Q2": ("2026-04-01", "2026-05-01", "2026-06-01"),
}


def load_catalogs() -> tuple[
    dict[str, dict], dict[str, list[str]], list[str], dict[str, list[str]]
]:
    services = json.loads((REPO_ROOT / "config" / "services.json").read_text())
    units = {
        item["unit_id"]: item
        for item in services["organizational_units"]
        if item.get("mvp_enabled")
    }
    specialties: dict[str, list[str]] = {unit_id: [] for unit_id in units}
    for item in services["analytical_specialties"]:
        if item.get("mvp_enabled") and item["parent_unit_id"] in specialties:
            specialties[item["parent_unit_id"]].append(item["specialty_id"])
    for values in specialties.values():
        values.sort()
    with (
        REPO_ROOT / "data" / "reference" / "deis_establishments_ssmc_snapshot.csv"
    ).open("r", encoding="utf-8", newline="") as handle:
        origins = sorted(
            row["establishment_code"]
            for row in csv.DictReader(handle)
            if row["coordinates_available"].casefold() == "true"
            and row["establishment_code"] != HEC_DEIS_CODE
            and row["commune_name"]
            in {"Maipú", "Cerrillos", "Estación Central", "Santiago"}
        )
    diagnosis_contract = json.loads(
        (REPO_ROOT / "config" / "referral_diagnoses.json").read_text(
            encoding="utf-8"
        )
    )
    diagnoses_by_specialty: dict[str, list[str]] = {}
    for item in diagnosis_contract["diagnoses"]:
        if (
            item.get("status") == "active_mvp"
            and item.get("classification") == "simulated_demo"
        ):
            diagnoses_by_specialty.setdefault(item["specialty_id"], []).append(
                item["diagnosis_group_id"]
            )
    for values in diagnoses_by_specialty.values():
        values.sort()
    return units, specialties, origins, diagnoses_by_specialty


def coverage_strata(
    units: dict[str, dict],
    specialties: dict[str, list[str]],
    dashboard_type: str,
) -> list[tuple[str, str]]:
    """Return every selectable service/specialty leaf in stable order."""

    strata: list[tuple[str, str]] = []
    for service_id in sorted(
        unit_id
        for unit_id, item in units.items()
        if item["dashboard_type"] == dashboard_type
    ):
        values = specialties[service_id]
        strata.extend((service_id, specialty_id) for specialty_id in values)
        if not values:
            strata.append((service_id, ""))
    return strata


def yes_no(value: bool) -> str:
    return "SI" if value else "NO"


def _trend(stratum_index: int) -> int:
    """Cycle through deterioration (-1), stability (0), and improvement (1)."""

    return (stratum_index % 3) - 1


def build_referrals(
    rng: random.Random,
    clinical_strata: list[tuple[str, str]],
    origins: list[str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    record_index = 0
    target_by_quarter = {"Q1": 1_704, "Q2": 1_696}
    counts_by_quarter: dict[str, list[int]] = {}
    for quarter in ("Q1", "Q2"):
        target_per_quarter = target_by_quarter[quarter]
        base_count, remainder = divmod(
            target_per_quarter, len(clinical_strata)
        )
        counts = []
        for stratum_index in range(len(clinical_strata)):
            trend = _trend(stratum_index)
            trend_adjustment = 4 * trend if quarter == "Q2" else -4 * trend
            counts.append(
                base_count
                + (1 if stratum_index < remainder else 0)
                + trend_adjustment
            )
        counts[-1] += target_per_quarter - sum(counts)
        if min(counts) < 80:
            raise RuntimeError(
                "Referral coverage requires at least 80 rows per stratum and quarter"
            )
        counts_by_quarter[quarter] = counts
    for stratum_index, (service_id, specialty_id) in enumerate(clinical_strata):
        trend = _trend(stratum_index)
        for quarter_index, quarter in enumerate(("Q1", "Q2")):
            # Reserve the relevant denominators instead of relying on random luck.
            count = counts_by_quarter[quarter][stratum_index]
            for local_index in range(count):
                record_index += 1
                referral_type = (
                    "new"
                    if local_index < 40
                    else "followup"
                    if local_index < 80
                    else "teleconsult"
                )
                scheduled = local_index < 80 or local_index % 7 != 0
                phase = (local_index + stratum_index * 3) % 40
                no_show_threshold = (
                    5 - (trend if quarter == "Q2" else 0)
                    if referral_type == "new"
                    else 4 + (trend if quarter == "Q2" else 0)
                )
                no_show = (
                    referral_type in {"new", "followup"}
                    and scheduled
                    and phase < max(2, no_show_threshold)
                )
                status_phase = (local_index + stratum_index) % 10
                status = (
                    "waiting"
                    if status_phase < 2
                    else "discharged"
                    if status_phase < 4
                    else "completed"
                )
                ges_applicable = (local_index + stratum_index) % 5 == 0
                ges_due = ges_applicable and local_index % 4 != 0
                period_effect = -4 * trend if quarter == "Q2" else 0
                rows.append(
                    {
                        "referral_id": f"SIM-REF-{record_index:06d}",
                        "period_date": PERIOD_MONTHS[quarter][
                            (local_index + stratum_index) % 3
                        ],
                        "service_id": service_id,
                        "specialty_id": specialty_id,
                        "origin_establishment_code": origins[
                            (record_index + stratum_index) % 12
                        ],
                        "referral_type": referral_type,
                        "status": status,
                        "wait_days": max(
                            0,
                            round(
                                rng.gauss(
                                    48 + (stratum_index % 5) * 4 + period_effect,
                                    13,
                                )
                            ),
                        ),
                        "scheduled_flag": yes_no(scheduled),
                        "no_show_flag": yes_no(no_show),
                        "pertinence_assessment": (
                            "not_assessed"
                            if local_index % 13 == 0
                            else "not_pertinent"
                            if (local_index + stratum_index + quarter_index) % 9 == 0
                            else "pertinent"
                        ),
                        "contrareference_flag": yes_no(
                            status == "discharged" and local_index % 4 != 0
                        ),
                        "ges_applicable_flag": yes_no(ges_applicable),
                        "ges_due_flag": yes_no(ges_due),
                        "ges_met_flag": yes_no(
                            ges_due and (local_index + quarter_index + trend) % 11 != 0
                        ),
                        "teleconsult_timely_closed_flag": yes_no(
                            referral_type == "teleconsult"
                            and (local_index + stratum_index + quarter_index) % 6 != 0
                        ),
                        "documentation_complete_flag": yes_no(
                            (local_index + stratum_index * 2) % 25 != 0
                        ),
                    }
                )
    return rows


def build_surgeries(
    rng: random.Random,
    surgical_strata: list[tuple[str, str]],
    origins: list[str],
) -> list[dict[str, object]]:
    procedures = ("PROC-CMA", "PROC-CIR", "PROC-TRA", "PROC-URO", "PROC-ORL")
    rows: list[dict[str, object]] = []
    record_index = 0
    for stratum_index, (service_id, specialty_id) in enumerate(surgical_strata):
        trend = _trend(stratum_index)
        for quarter_index, quarter in enumerate(("Q1", "Q2")):
            waitlisted_count = 40 - (4 * trend if quarter == "Q2" else 0)
            completed_count = 40
            suspended_count = 10 - (2 * trend if quarter == "Q2" else 0)
            for local_index in range(100):
                record_index += 1
                rank = (local_index + stratum_index * 7) % 100
                if rank < waitlisted_count:
                    status = "waitlisted"
                elif rank < waitlisted_count + completed_count:
                    status = "completed"
                elif rank < waitlisted_count + completed_count + suspended_count:
                    status = "suspended"
                else:
                    status = "resolved"
                elective = status in {"completed", "suspended", "resolved"} or rank % 5 != 0
                ambulatory = (
                    status == "completed"
                    and elective
                    and (rank + quarter_index + stratum_index) % 10
                    < 5 + (1 if quarter == "Q2" and trend > 0 else 0)
                )
                scheduled = status != "waitlisted"
                available = (4.0, 6.0, 8.0)[(local_index + stratum_index) % 3]
                if status == "waitlisted":
                    used = 0.0
                elif status == "suspended":
                    used = round(available * 0.12, 2)
                else:
                    used = round(available * rng.uniform(0.62, 0.96), 2)
                period_effect = -6 * trend if quarter == "Q2" else 0
                rows.append(
                    {
                        "surgery_case_id": f"SIM-SUR-{record_index:06d}",
                        "period_date": PERIOD_MONTHS[quarter][
                            (local_index + stratum_index) % 3
                        ],
                        "service_id": service_id,
                        "specialty_id": specialty_id,
                        "origin_establishment_code": origins[
                            (record_index + stratum_index * 2) % 12
                        ],
                        "procedure_code": procedures[
                            (local_index + stratum_index) % len(procedures)
                        ],
                        "status": status,
                        "wait_days": max(
                            0,
                            round(
                                rng.gauss(
                                    82 + (stratum_index % 4) * 6 + period_effect,
                                    21,
                                )
                            ),
                        ),
                        "elective_major_flag": yes_no(elective),
                        "ambulatory_flag": yes_no(ambulatory),
                        "scheduled_flag": yes_no(scheduled),
                        "or_hours_used": used,
                        "or_hours_available": available,
                        "documentation_complete_flag": yes_no(
                            (local_index + stratum_index + quarter_index) % 34 != 0
                        ),
                    }
                )
    return rows


def build_professional_activity(
    profiles: list[dict[str, object]],
    origins: list[str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    record_index = 0
    for profile_index, profile in enumerate(profiles):
        profile_key = str(profile["professional_id"])
        profile_type = str(profile["profile_type"])
        lenses = list(profile["supported_lenses"])
        for lens_index, lens_value in enumerate(lenses):
            lens = str(lens_value)
            if profile_type == "mixed":
                lens_context = profile["lens_contexts"][lens]  # type: ignore[index]
                service_id = str(lens_context["service_id"])
                specialty_id = str(lens_context["specialty_id"])
            else:
                service_id = str(profile["service_id"])
                specialty_id = str(profile["specialty_id"])
            for quarter_index, quarter in enumerate(("Q1", "Q2")):
                trend = _trend(profile_index + lens_index)
                completion_limit = 50 + (
                    2 * trend if quarter == "Q2" else 0
                )
                for local_index in range(60):
                    record_index += 1
                    rank = (
                        local_index + profile_index * 7 + lens_index * 13
                    ) % 60
                    scheduled = rank < 56
                    completed = scheduled and rank < completion_limit
                    clinical = lens == "clinical"
                    elective_applicable = not clinical and rank < 50
                    new_consultation = clinical and completed and rank % 10 < 4
                    no_show = (
                        clinical
                        and scheduled
                        and not completed
                        and rank % 3 != 0
                    )
                    suspended = (
                        not clinical
                        and scheduled
                        and not completed
                        and rank % 2 == 0
                    )
                    ambulatory_limit = 27 + (
                        2 * trend if quarter == "Q2" else 0
                    )
                    ambulatory = (
                        elective_applicable
                        and (rank + profile_index + lens_index) % 50
                        < max(23, ambulatory_limit)
                    )
                    documentation_complete = (
                        rank + profile_index + quarter_index
                    ) % 20 != 0
                    if clinical:
                        activity_code = (
                            "CONS-NUEVA"
                            if new_consultation
                            else "TELECONS"
                            if rank % 7 == 0
                            else "CONS-CONTROL"
                        )
                    else:
                        activity_code = ("PROC-CMA", "PROC-CIR", "PROC-TRA")[
                            (local_index + profile_index) % 3
                        ]
                    rows.append(
                        {
                            "activity_id": f"SIM-ACT-{record_index:06d}",
                            "period_date": PERIOD_MONTHS[quarter][
                                (local_index + profile_index + lens_index) % 3
                            ],
                            "simulated_profile_key": profile_key,
                            "profile_type": profile_type,
                            "lens": lens,
                            "service_id": service_id,
                            "specialty_id": specialty_id,
                            "origin_establishment_code": origins[
                                (record_index + profile_index + lens_index) % 12
                            ],
                            "activity_code": activity_code,
                            "scheduled_flag": yes_no(scheduled),
                            "completed_flag": yes_no(completed),
                            "no_show_flag": yes_no(no_show),
                            "suspended_flag": yes_no(suspended),
                            "new_consultation_flag": yes_no(new_consultation),
                            "discharge_flag": yes_no(
                                clinical and completed and rank % 7 == 0
                            ),
                            "elective_major_applicable_flag": yes_no(
                                elective_applicable
                            ),
                            "ambulatory_major_flag": yes_no(ambulatory),
                            "documentation_complete_flag": yes_no(
                                documentation_complete
                            ),
                        }
                    )
    return rows


def build_ambulatory_waitlist(
    specialties: list[tuple[str, str]],
    origins: list[str],
    profiles: list[dict[str, object]],
    diagnoses_by_specialty: dict[str, list[str]],
) -> list[dict[str, object]]:
    """Build 60 deterministic episodes per specialty, queue and quarter."""

    profiles_by_scope: dict[tuple[str, str], list[str]] = {}
    for profile in profiles:
        profiles_by_scope.setdefault(
            (str(profile["service_id"]), str(profile["specialty_id"])), []
        ).append(str(profile["professional_id"]))
    rows: list[dict[str, object]] = []
    record_index = 0
    snapshots = {"Q1": date(2026, 3, 31), "Q2": date(2026, 6, 30)}
    exit_reasons = ("clinical_exit", "duplicate", "declined", "other_valid")
    followup_prestations = (
        "control_especialidad",
        "evaluacion_preoperatoria",
        "procedimiento_ambulatorio",
    )
    for stratum_index, (service_id, specialty_id) in enumerate(specialties):
        profile_ids = profiles_by_scope[(service_id, specialty_id)]
        diagnosis_ids = diagnoses_by_specialty[specialty_id]
        if len(diagnosis_ids) < 4:
            raise RuntimeError(
                f"At least four simulated referral diagnoses are required for {specialty_id}"
            )
        trend = _trend(stratum_index)
        for quarter_index, quarter in enumerate(("Q1", "Q2")):
            snapshot = snapshots[quarter]
            period_effect = -12 * trend if quarter == "Q2" else 0
            specialty_hash = int(
                sha256(specialty_id.encode("utf-8")).hexdigest()[:8], 16
            )
            origin_step = (1, 5, 7, 11)[stratum_index % 4]
            origin_order = [
                origins[(specialty_hash % 12 + rank * origin_step) % 12]
                for rank in range(12)
            ]
            if quarter == "Q1":
                origin_counts = [30, 30, 20, 20, 10, 10, 0, 0, 0, 0, 0, 0]
            else:
                origin_counts = (
                    [40, 30, 20, 10, 10, 10, 0, 0, 0, 0, 0, 0],
                    [30, 30, 20, 20, 10, 10, 0, 0, 0, 0, 0, 0],
                    [30, 20, 20, 20, 20, 10, 0, 0, 0, 0, 0, 0],
                    [50, 20, 20, 10, 10, 10, 0, 0, 0, 0, 0, 0],
                    [40, 20, 20, 20, 10, 10, 0, 0, 0, 0, 0, 0],
                    [30, 30, 30, 10, 10, 10, 0, 0, 0, 0, 0, 0],
                    [40, 40, 10, 10, 10, 10, 0, 0, 0, 0, 0, 0],
                )[stratum_index % 7]
            origin_sequence = [
                code
                for code, count in zip(origin_order, origin_counts)
                for _ in range(count)
            ]
            if len(origin_sequence) != 120:
                raise RuntimeError("Origin weighting must allocate exactly 120 rows")
            local_rng = random.Random(
                SEED + stratum_index * 101 + quarter_index * 17
            )
            local_rng.shuffle(origin_sequence)
            origin_rank = {code: rank for rank, code in enumerate(origin_order)}
            occurrence_by_origin: dict[str, int] = {}
            for queue_index, queue_type in enumerate(
                ("new_consultation", "followup_control")
            ):
                for local_index in range(60):
                    record_index += 1
                    position = queue_index * 60 + local_index
                    origin_code = origin_sequence[position]
                    occurrence = occurrence_by_origin.get(origin_code, 0)
                    occurrence_by_origin[origin_code] = occurrence + 1
                    dominant_diagnosis = (
                        origin_rank[origin_code] + stratum_index
                    ) % len(diagnosis_ids)
                    center_count = origin_counts[origin_rank[origin_code]]
                    diagnosis_index = (
                        dominant_diagnosis
                        if occurrence < max(10, center_count - 10)
                        else (dominant_diagnosis + 1) % len(diagnosis_ids)
                    )
                    referral_diagnosis_id = diagnosis_ids[diagnosis_index]
                    shared_professional_scope = (
                        queue_type == "followup_control" and len(profile_ids) > 1
                    )
                    if shared_professional_scope:
                        status = (
                            "open_unscheduled"
                            if local_index % 30 < 15
                            else "open_scheduled"
                        )
                    elif local_index < 18:
                        status = "open_unscheduled"
                    elif local_index < 34:
                        status = "open_scheduled"
                    elif local_index < 54:
                        status = "completed"
                    else:
                        status = "exited"
                    age_days = max(
                        5,
                        25
                        + (stratum_index % 6) * 13
                        + (local_index * 7) % 85
                        + queue_index * 9
                        + period_effect,
                    )
                    index_date = snapshot - timedelta(days=age_days)
                    completion_date: date | None = None
                    scheduled_date: date | None = None
                    exit_reason = ""
                    if status == "open_scheduled":
                        scheduled_date = snapshot + timedelta(
                            days=1 + ((local_index + stratum_index) % 30)
                        )
                    elif status == "completed":
                        completion_date = index_date + timedelta(
                            days=max(1, age_days - (local_index % 18))
                        )
                    elif status == "exited":
                        exit_reason = exit_reasons[
                            (local_index + stratum_index + quarter_index) % len(exit_reasons)
                        ]
                    is_new = queue_type == "new_consultation"
                    rows.append(
                        {
                            "wait_episode_id": f"SIM-WAIT-{record_index:06d}",
                            "snapshot_date": snapshot.isoformat(),
                            "period_id": f"2026-{quarter}",
                            "queue_type": queue_type,
                            "service_id": service_id,
                            "specialty_id": specialty_id,
                            "referral_diagnosis_id": referral_diagnosis_id,
                            "professional_profile_id": (
                                profile_ids[
                                    min(local_index // 30, len(profile_ids) - 1)
                                    if shared_professional_scope
                                    else 0
                                ]
                                if not is_new or local_index % 3 == 0
                                else ""
                            ),
                            "origin_deis_code": origin_code,
                            "requested_prestation": (
                                "consulta_nueva"
                                if is_new
                                else followup_prestations[
                                    (local_index + stratum_index) % len(followup_prestations)
                                ]
                            ),
                            "queue_entry_date": index_date.isoformat() if is_new else "",
                            "control_due_date": "" if is_new else index_date.isoformat(),
                            "scheduled_date": (
                                scheduled_date.isoformat() if scheduled_date else ""
                            ),
                            "completion_date": (
                                completion_date.isoformat() if completion_date else ""
                            ),
                            "episode_status": status,
                            "exit_reason": exit_reason,
                            "priority_class": ("routine", "preferential", "urgent")[
                                (local_index + stratum_index) % 3
                            ],
                            "simulated_flag": "SI",
                        }
                    )
    return rows


def generate_dataset() -> tuple[dict[str, list[dict[str, object]]], dict[str, object]]:
    rng = random.Random(SEED)
    units, specialties, origins, diagnoses_by_specialty = load_catalogs()
    if len(origins) < 12:
        raise RuntimeError("At least 12 mapped DEIS origins are required")
    profile_contract = json.loads(
        (REPO_ROOT / "config" / "professional_profiles.json").read_text(
            encoding="utf-8"
        )
    )
    professional_profiles = [
        profile
        for profile in profile_contract["profiles"]
        if profile.get("mvp_enabled") and profile.get("simulated") is True
    ]
    for profile in professional_profiles:
        if profile["profile_type"] != "mixed":
            continue
        for lens, activity_class in (
            ("clinical", "outpatient_clinical"),
            ("surgical", "surgical_procedural"),
        ):
            context = profile["lens_contexts"][lens]
            if any(
                context.get(field) != profile.get(field)
                for field in (
                    "service_id",
                    "specialty_id",
                    "specialty_display_name",
                )
            ) or context.get("activity_class") != activity_class:
                raise RuntimeError(
                    "Mixed profile lenses must preserve one identity and specialty"
                )
    clinical_strata = coverage_strata(units, specialties, "clinical")
    clinical_strata.extend(
        (profile["service_id"], profile["specialty_id"])
        for profile in professional_profiles
        if profile["profile_type"] == "mixed"
        and profile["lens_contexts"]["clinical"]["activity_class"]
        == "outpatient_clinical"
        and (profile["service_id"], profile["specialty_id"])
        not in clinical_strata
    )
    clinical_strata.sort()
    surgical_strata = coverage_strata(units, specialties, "surgical")
    waitlist_strata = sorted(
        (item["parent_unit_id"], item["specialty_id"])
        for item in json.loads(
            (REPO_ROOT / "config" / "services.json").read_text(encoding="utf-8")
        )["analytical_specialties"]
        if item.get("mvp_enabled")
    )
    tables = {
        "DERIVACIONES": build_referrals(rng, clinical_strata, origins),
        "CIRUGIAS": build_surgeries(rng, surgical_strata, origins),
        "ACTIVIDAD_PROF": build_professional_activity(
            professional_profiles, origins
        ),
        "LISTA_ESPERA_AMB": build_ambulatory_waitlist(
            waitlist_strata,
            origins,
            professional_profiles,
            diagnoses_by_specialty,
        ),
    }
    metadata: dict[str, object] = {
        "contract_version": "1.3.0",
        "dataset_id": DATASET_ID,
        "dataset_name": DATASET_NAME,
        "source_mode": "simulado",
        "period_start": "2026-01-01",
        "period_end": "2026-06-30",
        "generated_at_utc": GENERATED_AT_UTC,
        "simulation_notice_es": (
            "Datos operacionales y perfiles profesionales completamente simulados."
        ),
        "deis_snapshot_id": "deis_ssmc_2026-08-25_etl-0.1.0",
        "seed": SEED,
        "coverage_design": {
            "clinical_service_specialty_strata": len(clinical_strata),
            "surgical_service_specialty_strata": len(surgical_strata),
            "minimum_new_scheduled_per_stratum_period": 40,
            "minimum_followup_scheduled_per_stratum_period": 40,
            "minimum_elective_completed_per_stratum_period": 40,
            "professional_rows_per_profile_lens_period": 60,
            "professional_profiles": len(professional_profiles),
            "professional_clinical_specialties": sum(
                profile["profile_type"] == "clinical"
                for profile in professional_profiles
            ),
            "professional_surgical_specialties": sum(
                profile["profile_type"] == "surgical"
                for profile in professional_profiles
            ),
            "professional_mixed_arrangements": sum(
                profile["profile_type"] == "mixed"
                for profile in professional_profiles
            ),
            "waitlist_specialties": len(waitlist_strata),
            "waitlist_rows_per_specialty_queue_period": 60,
            "waitlist_queue_types": 2,
            "waitlist_periods": 2,
            "referral_diagnosis_groups": sum(
                len(values) for values in diagnoses_by_specialty.values()
            ),
            "heterogeneous_origin_model": (
                "base propensity + specialty affinity + diagnosis-center affinity + period trend; seed 617"
            ),
        },
        "row_counts": {name: len(rows) for name, rows in tables.items()},
    }
    return tables, metadata


def _csv_text(rows: list[dict[str, object]]) -> str:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def write_outputs(
    output_dir: Path,
    tables: dict[str, list[dict[str, object]]],
    metadata: dict[str, object],
) -> dict[str, bytes]:
    output_dir.mkdir(parents=True, exist_ok=True)
    names = {
        "DERIVACIONES": "derivaciones_simuladas.csv",
        "CIRUGIAS": "cirugias_simuladas.csv",
        "ACTIVIDAD_PROF": "actividad_profesional_simulada.csv",
        "LISTA_ESPERA_AMB": "lista_espera_ambulatoria_simulada.csv",
    }
    artifacts = {
        filename: _csv_text(tables[sheet]).encode("utf-8")
        for sheet, filename in names.items()
    }
    metadata["artifact_checksums_sha256"] = {
        filename: sha256(content).hexdigest()
        for filename, content in artifacts.items()
    }
    artifacts["metadata.json"] = (
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    for filename, content in artifacts.items():
        (output_dir / filename).write_bytes(content)
    return artifacts


def _column_letter(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell_xml(reference: str, value: object, style: int) -> str:
    text = "" if value is None else str(value)
    return (
        f'<x:c r="{reference}" s="{style}" t="str">'
        f"<x:v>{escape(text)}</x:v></x:c>"
    )


def _sheet_data_xml(
    headers: list[str], rows: list[list[object]], *, metadata: bool = False
) -> str:
    content = ["<x:sheetData>"]
    header_style = 12 if metadata else 26
    header_height = "" if metadata else ' ht="42" customHeight="1"'
    content.append(f'<x:row r="1"{header_height}>')
    for column, value in enumerate(headers):
        content.append(_cell_xml(f"{_column_letter(column)}1", value, header_style))
    content.append("</x:row>")
    for row_number, row in enumerate(rows, start=2):
        row_height = "" if metadata else ' ht="20" customHeight="1"'
        content.append(f'<x:row r="{row_number}"{row_height}>')
        for column, value in enumerate(row):
            style = 13 if metadata and column == 0 else 21 if metadata else 27
            content.append(
                _cell_xml(f"{_column_letter(column)}{row_number}", value, style)
            )
        content.append("</x:row>")
    content.append("</x:sheetData>")
    return "".join(content)


def _replace_sheet_data(xml_text: str, replacement: str) -> str:
    updated, count = re.subn(
        r"<x:sheetData>.*?</x:sheetData>", replacement, xml_text, flags=re.DOTALL
    )
    if count != 1:
        raise RuntimeError("Workbook sheetData replacement was not unique")
    return updated


def _extend_validations(xml_text: str, final_row: int) -> str:
    return re.sub(
        r'sqref="([A-Z]+2:[A-Z]+)\d+"',
        lambda match: f'sqref="{match.group(1)}{final_row}"',
        xml_text,
    )


def update_workbook(
    source_workbook: Path,
    target_workbook: Path,
    tables: dict[str, list[dict[str, object]]],
    metadata: dict[str, object],
) -> None:
    workbook_metadata_keys = (
        "contract_version",
        "dataset_id",
        "dataset_name",
        "source_mode",
        "period_start",
        "period_end",
        "generated_at_utc",
        "simulation_notice_es",
        "deis_snapshot_id",
    )
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(source_workbook, "r") as archive:
        sheet_specs = {
            "xl/worksheets/sheet2.xml": (
                ["clave", "valor"],
                [[key, metadata[key]] for key in workbook_metadata_keys],
                True,
            ),
            "xl/worksheets/sheet3.xml": (
                list(tables["DERIVACIONES"][0]),
                [list(row.values()) for row in tables["DERIVACIONES"]],
                False,
            ),
            "xl/worksheets/sheet4.xml": (
                list(tables["CIRUGIAS"][0]),
                [list(row.values()) for row in tables["CIRUGIAS"]],
                False,
            ),
            "xl/worksheets/sheet5.xml": (
                list(tables["ACTIVIDAD_PROF"][0]),
                [list(row.values()) for row in tables["ACTIVIDAD_PROF"]],
                False,
            ),
            "xl/worksheets/sheet7.xml": (
                list(tables["LISTA_ESPERA_AMB"][0]),
                [list(row.values()) for row in tables["LISTA_ESPERA_AMB"]],
                False,
            ),
        }
        for path, (headers, rows, is_metadata) in sheet_specs.items():
            xml_text = archive.read(path).decode("utf-8")
            xml_text = _replace_sheet_data(
                xml_text, _sheet_data_xml(headers, rows, metadata=is_metadata)
            )
            if not is_metadata:
                xml_text = _extend_validations(xml_text, max(15000, len(rows) + 100))
            replacements[path] = xml_text.encode("utf-8")

        table_rows = {
            "xl/tables/table1.xml": ("B", len(workbook_metadata_keys) + 1),
            "xl/tables/table2.xml": ("Q", len(tables["DERIVACIONES"]) + 1),
            "xl/tables/table3.xml": ("N", len(tables["CIRUGIAS"]) + 1),
            "xl/tables/table4.xml": ("R", len(tables["ACTIVIDAD_PROF"]) + 1),
            "xl/tables/table6.xml": ("R", len(tables["LISTA_ESPERA_AMB"]) + 1),
        }
        for path, (last_column, final_row) in table_rows.items():
            xml_text = archive.read(path).decode("utf-8")
            xml_text, count = re.subn(
                r'ref="A1:[A-Z]+\d+"',
                f'ref="A1:{last_column}{final_row}"',
                xml_text,
                count=1,
            )
            if count != 1:
                raise RuntimeError(f"Table range replacement failed for {path}")
            replacements[path] = xml_text.encode("utf-8")

        target_workbook.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix="hec_day5_", suffix=".xlsx", dir=target_workbook.parent, delete=False
        ) as handle:
            temporary_path = Path(handle.name)
        try:
            with zipfile.ZipFile(temporary_path, "w") as output:
                for info in archive.infolist():
                    output.writestr(info, replacements.get(info.filename, archive.read(info)))
            temporary_path.replace(target_workbook)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--workbook-source", type=Path, default=DEFAULT_WORKBOOK_SOURCE)
    parser.add_argument("--workbook-output", type=Path, default=DEFAULT_WORKBOOK_OUTPUT)
    parser.add_argument("--skip-workbook", action="store_true")
    args = parser.parse_args()

    tables, metadata = generate_dataset()
    write_outputs(args.output_dir, tables, metadata)
    if not args.skip_workbook:
        update_workbook(args.workbook_source, args.workbook_output, tables, metadata)
    counts = metadata["row_counts"]
    print(
        "PASS simulated data: "
        f"{counts['DERIVACIONES']} referrals; "
        f"{counts['CIRUGIAS']} surgeries; "
        f"{counts['ACTIVIDAD_PROF']} professional activities; "
        f"{counts['LISTA_ESPERA_AMB']} ambulatory waitlist episodes; "
        f"total={sum(counts.values())}; seed={SEED}; dataset={DATASET_ID}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
