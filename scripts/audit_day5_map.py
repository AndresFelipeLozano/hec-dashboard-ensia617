#!/usr/bin/env python3
"""Executable differentiation and reconciliation audit for the Day 5 map."""

from __future__ import annotations

import argparse
import copy
from datetime import date
import json
import math
from pathlib import Path
import sys
from time import perf_counter


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from hec_dashboard.app_config import load_contract  # noqa: E402
from hec_dashboard.data_ingestion import CandidateDataset, validate_tables  # noqa: E402
from hec_dashboard.visual_analytics import (  # noqa: E402
    HEC_DEIS_CODE,
    diagnosis_options,
    hec_marker,
    map_signature,
    origin_bubbles,
    referring_center_diagnoses,
    referring_center_specialties,
    rows_to_csv,
    scoped_network_rows,
    scoped_waitlist_rows,
)
from validate_data_contract import load_simulated_tables  # noqa: E402


Q1 = (date(2026, 1, 1), date(2026, 3, 31))
Q2 = (date(2026, 4, 1), date(2026, 6, 30))
REPRESENTATIVE_SPECIALTIES = (
    "urologia",
    "neurologia_infantil",
    "cardiologia_adulto",
    "cirugia_general",
    "traumatologia",
)
ORIGIN_FIELDS = {
    "DERIVACIONES": "origin_establishment_code",
    "CIRUGIAS": "origin_establishment_code",
    "ACTIVIDAD_PROF": "origin_establishment_code",
    "LISTA_ESPERA_AMB": "origin_deis_code",
}


def _data_signature(rows: list[dict]) -> tuple:
    return tuple(
        (
            row["Código DEIS"],
            row["Episodios"],
            row["Variación"],
            row["Especialidad predominante"],
            row["Diagnóstico predominante"],
        )
        for row in rows
    )


def _context_summary(
    dataset: CandidateDataset, name: str, context: dict, failures: list[dict]
) -> dict:
    rows = origin_bubbles(dataset, Q2, Q1, context, repo_root=REPO_ROOT)
    scoped = scoped_network_rows(dataset, Q2, context)
    mapped_total = sum(row["Episodios"] for row in rows)
    if mapped_total != len(scoped):
        failures.append(
            {"check": "map_table_reconciliation", "context": name, "mapped": mapped_total, "scoped": len(scoped)}
        )
    if any(
        not math.isfinite(float(row["Episodios"]))
        or row["Episodios"] <= 0
        or (row["Latitud"], row["Longitud"]) == (0.0, 0.0)
        for row in rows
    ):
        failures.append({"check": "invalid_bubble", "context": name})
    if any(row["Código DEIS"] == HEC_DEIS_CODE for row in rows):
        failures.append({"check": "hec_external_origin", "context": name})
    accessible_rows = [
        {key: value for key, value in row.items() if key not in {"Latitud", "Longitud"}}
        for row in rows
    ]
    if HEC_DEIS_CODE in rows_to_csv(accessible_rows).decode("utf-8-sig"):
        failures.append({"check": "hec_external_csv", "context": name})
    return {
        "context": name,
        "filtered_total": len(scoped),
        "active_establishments": len(rows),
        "top_three": [
            {"deis_code": row["Código DEIS"], "episodes": row["Episodios"]}
            for row in rows[:3]
        ],
        "bubble_size_signature": [row["Episodios"] for row in rows],
        "dominant_signature": [
            row["Diagnóstico predominante"]
            if context.get("specialty_id")
            else row["Especialidad predominante"]
            for row in rows
        ],
        "current_comparison_vector": [row["Variación"] for row in rows],
        "map_signature": map_signature(rows, dataset, Q2, Q1, context),
        "accessible_table_reconciled": mapped_total == len(scoped),
        "data_signature": _data_signature(rows),
    }


def audit() -> dict[str, object]:
    started = perf_counter()
    failures: list[dict] = []
    report = validate_tables(copy.deepcopy(load_simulated_tables(REPO_ROOT)), REPO_ROOT)
    if not report.activatable or report.rejected_row_count:
        failures.append({"check": "packaged_dataset", "summary": report.summary()})
    dataset = CandidateDataset(report.metadata, report.accepted_rows, report.summary())
    packaged_hec_origins = {
        sheet: sum(
            str(row.get(field)) == HEC_DEIS_CODE
            for row in dataset.tables.get(sheet, [])
        )
        for sheet, field in ORIGIN_FIELDS.items()
    }
    if any(packaged_hec_origins.values()):
        failures.append(
            {"check": "packaged_hec_external_origin", "counts": packaged_hec_origins}
        )
    marker = hec_marker(REPO_ROOT)
    if marker.get("Código DEIS") != HEC_DEIS_CODE:
        failures.append({"check": "hec_destination_marker", "marker": marker})
    contexts: list[tuple[str, dict]] = [
        ("institutional_overview", {"role_id": "director"}),
        ("medical_director_overview", {"role_id": "medical_director"}),
    ]
    services = load_contract("services")["analytical_specialties"]
    specialty_scope = {
        item["specialty_id"]: item["parent_unit_id"]
        for item in services
        if item.get("mvp_enabled")
    }
    for specialty_id, service_id in sorted(specialty_scope.items()):
        contexts.append(
            (
                f"director_{specialty_id}",
                {
                    "role_id": "director",
                    "service_id": service_id,
                    "specialty_id": specialty_id,
                },
            )
        )
    profiles = load_contract("professional_profiles")["profiles"]
    clinical_profile = next(item for item in profiles if item["profile_type"] == "clinical")
    surgical_profile = next(item for item in profiles if item["profile_type"] == "surgical")
    mixed_profile = next(item for item in profiles if item["profile_type"] == "mixed")
    contexts.extend(
        [
            (
                "clinical_professional",
                {
                    "role_id": "professional_clinical",
                    "service_id": clinical_profile["service_id"],
                    "specialty_id": clinical_profile["specialty_id"],
                    "simulated_profile_key": clinical_profile["professional_id"],
                    "professional_lens": "clinical",
                },
            ),
            (
                "surgical_professional",
                {
                    "role_id": "professional_surgical",
                    "service_id": surgical_profile["service_id"],
                    "specialty_id": surgical_profile["specialty_id"],
                    "simulated_profile_key": surgical_profile["professional_id"],
                    "professional_lens": "surgical",
                },
            ),
            (
                "mixed_clinical",
                {
                    "role_id": "professional_clinical",
                    "service_id": mixed_profile["service_id"],
                    "specialty_id": mixed_profile["specialty_id"],
                    "simulated_profile_key": mixed_profile["professional_id"],
                    "professional_lens": "clinical",
                },
            ),
            (
                "mixed_surgical",
                {
                    "role_id": "professional_surgical",
                    "service_id": mixed_profile["service_id"],
                    "specialty_id": mixed_profile["specialty_id"],
                    "simulated_profile_key": mixed_profile["professional_id"],
                    "professional_lens": "surgical",
                },
            ),
        ]
    )
    summaries = [
        _context_summary(dataset, name, context, failures)
        for name, context in contexts
    ]
    representative = {
        item["context"]: item
        for item in summaries
        if item["context"].removeprefix("director_") in REPRESENTATIVE_SPECIALTIES
    }
    representative_data_signatures = {
        item["data_signature"] for item in representative.values()
    }
    if len(representative_data_signatures) != len(REPRESENTATIVE_SPECIALTIES):
        failures.append(
            {"check": "material_specialty_signatures", "unique": len(representative_data_signatures)}
        )
    for specialty_id in REPRESENTATIVE_SPECIALTIES:
        context = {
            "role_id": "director",
            "service_id": specialty_scope[specialty_id],
            "specialty_id": specialty_id,
        }
        rows = scoped_network_rows(dataset, Q2, context)
        options = diagnosis_options(rows)
        if not options:
            failures.append({"check": "diagnosis_coverage", "specialty": specialty_id})
            continue
        diagnosis_context = {
            **context,
            "referral_diagnosis_id": options[0]["diagnosis_group_id"],
        }
        filtered = origin_bubbles(dataset, Q2, Q1, diagnosis_context)
        if not filtered or sum(row["Episodios"] for row in filtered) != len(
            scoped_network_rows(dataset, Q2, diagnosis_context)
        ):
            failures.append({"check": "diagnosis_map_reconciliation", "specialty": specialty_id})
    overview = origin_bubbles(dataset, Q2, Q1, {"role_id": "director"})
    center = overview[0]["Código DEIS"]
    specialty_breakdown = referring_center_specialties(
        dataset, Q2, Q1, {"role_id": "director"}, center
    )
    if sum(row["Actual"] for row in specialty_breakdown) != overview[0]["Episodios"]:
        failures.append({"check": "selected_center_specialty_reconciliation"})
    first_specialty = specialty_breakdown[0]["Especialidad ID"]
    diagnosis_context = {
        "role_id": "director",
        "service_id": specialty_scope[first_specialty],
        "specialty_id": first_specialty,
    }
    center_specialty_total = sum(
        row["origin_deis_code"] == center
        for row in scoped_network_rows(dataset, Q2, diagnosis_context)
    )
    diagnosis_breakdown = referring_center_diagnoses(
        dataset, Q2, diagnosis_context, center
    )
    if sum(row["Episodios"] for row in diagnosis_breakdown) != center_specialty_total:
        failures.append({"check": "selected_center_diagnosis_reconciliation"})
    catalog = load_contract("referral_diagnoses")["diagnoses"]
    catalog_by_id = {item["diagnosis_group_id"]: item for item in catalog}
    invalid = [
        row["wait_episode_id"]
        for row in dataset.tables["LISTA_ESPERA_AMB"]
        if row.get("referral_diagnosis_id") not in catalog_by_id
        or catalog_by_id[row["referral_diagnosis_id"]]["specialty_id"]
        != row["specialty_id"]
    ]
    if invalid:
        failures.append({"check": "diagnosis_compatibility", "rows": invalid[:10]})
    for item in summaries:
        item.pop("data_signature", None)
    return {
        "status": "PASS" if not failures else "FAIL",
        "dataset_id": dataset.metadata.get("dataset_id"),
        "contract_version": dataset.metadata.get("contract_version"),
        "contexts_checked": len(summaries),
        "representative_specialties": list(REPRESENTATIVE_SPECIALTIES),
        "packaged_hec_origin_counts": packaged_hec_origins,
        "hec_destination_marker_count": 1,
        "contexts": summaries,
        "failures": failures,
        "elapsed_seconds": round(perf_counter() - started, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = audit()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        f"{result['status']} Day 5 map: contexts={result['contexts_checked']}; "
        f"failures={len(result['failures'])}; elapsed={result['elapsed_seconds']}s"
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
