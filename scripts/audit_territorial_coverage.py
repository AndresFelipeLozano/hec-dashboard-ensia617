#!/usr/bin/env python3
"""Exhaustive deterministic territorial coverage and privacy audit."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import csv
from datetime import date
from io import StringIO
import json
import math
from pathlib import Path
import sys
from time import perf_counter


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_simulated_data import generate_dataset  # noqa: E402
from hec_dashboard.app_config import (  # noqa: E402
    load_contract,
    service_choices,
    specialty_choices,
)
from hec_dashboard.data_ingestion import CandidateDataset, validate_tables  # noqa: E402
from hec_dashboard.visual_analytics import (  # noqa: E402
    HEC_DEIS_CODE,
    center_waitlist_context,
    diagnosis_options,
    referring_center_diagnoses,
    referring_center_prestations,
    referring_center_specialties,
    rows_to_csv,
    scoped_network_rows,
    surgical_procedure_options,
    territorial_map_signature,
    territorial_scope_summary,
)
from validate_data_contract import load_simulated_tables  # noqa: E402


PERIODS = {
    "Q1": (
        (date(2026, 1, 1), date(2026, 3, 31)),
        (date(2026, 4, 1), date(2026, 6, 30)),
    ),
    "Q2": (
        (date(2026, 4, 1), date(2026, 6, 30)),
        (date(2026, 1, 1), date(2026, 3, 31)),
    ),
}
MINIMUM_CELL_N = 10
ORIGIN_FIELD = {
    "DERIVACIONES": "origin_establishment_code",
    "CIRUGIAS": "origin_establishment_code",
    "LISTA_ESPERA_AMB": "origin_deis_code",
}
FORBIDDEN_VISIBLE_FRAGMENTS = (
    "patient",
    "paciente_id",
    "rut",
    "referral_id",
    "surgery_case_id",
    "wait_episode_id",
    "professional_profile_id",
    "simulated_profile_key",
)


def supported_contexts(repo_root: Path = REPO_ROOT) -> list[dict]:
    """Enumerate every supported default context in a stable order."""

    contexts = [
        {"name": "director", "context": {"role_id": "director"}},
        {
            "name": "medical_director",
            "context": {"role_id": "medical_director"},
        },
    ]
    for dashboard_type, role_id in (
        ("clinical", "service_chief_clinical"),
        ("surgical", "service_chief_surgical"),
    ):
        for service in service_choices(dashboard_type, repo_root):
            service_id = service["unit_id"]
            base = {
                "role_id": role_id,
                "service_id": service_id,
                "specialty_id": None,
            }
            contexts.append(
                {
                    "name": f"{role_id}:service:{service_id}",
                    "context": base,
                }
            )
            for specialty in specialty_choices(service_id, repo_root):
                contexts.append(
                    {
                        "name": (
                            f"{role_id}:specialty:{specialty['specialty_id']}"
                        ),
                        "context": {
                            **base,
                            "specialty_id": specialty["specialty_id"],
                        },
                    }
                )
    profiles = load_contract("professional_profiles", repo_root)["profiles"]
    for profile in profiles:
        if not profile.get("mvp_enabled"):
            continue
        for lens in profile["supported_lenses"]:
            scope = (
                profile["lens_contexts"][lens]
                if profile["profile_type"] == "mixed"
                else profile
            )
            role_id = (
                "professional_clinical"
                if lens == "clinical"
                else "professional_surgical"
            )
            contexts.append(
                {
                    "name": f"{role_id}:{profile['professional_id']}:{lens}",
                    "context": {
                        "role_id": role_id,
                        "service_id": scope["service_id"],
                        "specialty_id": scope["specialty_id"],
                        "simulated_profile_key": profile["professional_id"],
                        "professional_lens": lens,
                    },
                }
            )
    return contexts


def _raw_scope_rows(
    dataset: CandidateDataset,
    period: tuple[date, date],
    context: dict,
    source: str,
) -> list[dict]:
    if source == "LISTA_ESPERA_AMB":
        return scoped_network_rows(dataset, period, context)
    field = ORIGIN_FIELD[source]
    rows = []
    for row in dataset.tables.get(source, []):
        if not period[0] <= row["period_date"] <= period[1]:
            continue
        if context.get("service_id") and row["service_id"] != context["service_id"]:
            continue
        if context.get("specialty_id") and row["specialty_id"] != context["specialty_id"]:
            continue
        if context.get("procedure_code") and row.get("procedure_code") != context["procedure_code"]:
            continue
        if str(row.get(field)) == HEC_DEIS_CODE:
            continue
        rows.append(row)
    return rows


def _data_signature(source: str, rows: list[dict]) -> tuple:
    return (
        source,
        tuple(
            (row["Código DEIS"], row["Episodios"], row["Variación"])
            for row in rows
        ),
    )


def _effective_scope(source: str, rows: list[dict]) -> tuple:
    return (
        source,
        tuple(sorted({row["service_id"] for row in rows})),
        tuple(sorted({row.get("specialty_id") or "" for row in rows})),
        tuple(sorted({row.get("procedure_code") or "" for row in rows})),
    )


def audit(repo_root: Path = REPO_ROOT) -> dict:
    started = perf_counter()
    failures: list[dict] = []
    report = validate_tables(
        copy.deepcopy(load_simulated_tables(repo_root)), repo_root
    )
    if not report.activatable or report.rejected_row_count:
        failures.append({"check": "packaged_dataset", "summary": report.summary()})
    dataset = CandidateDataset(
        report.metadata, report.accepted_rows, report.summary()
    )
    reference_path = (
        repo_root / "data" / "reference" / "deis_establishments_ssmc_snapshot.csv"
    )
    with reference_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reference = {
            row["establishment_code"]: row for row in csv.DictReader(handle)
        }

    contexts = supported_contexts(repo_root)
    summaries = []
    mixed_signatures: dict[tuple[str, str], tuple] = {}
    marker_counts = []
    for item in contexts:
        name = item["name"]
        context = item["context"]
        for period_name, (current, previous) in PERIODS.items():
            summary = territorial_scope_summary(
                dataset,
                current,
                previous,
                context,
                minimum_cell_n=MINIMUM_CELL_N,
                repo_root=repo_root,
            )
            rows = summary["rows"]
            raw = _raw_scope_rows(dataset, current, context, summary["source"])
            prior_raw = _raw_scope_rows(
                dataset, previous, context, summary["source"]
            )
            field = ORIGIN_FIELD[summary["source"]]
            current_counts = Counter(row[field] for row in raw)
            previous_counts = Counter(row[field] for row in prior_raw)
            expected_codes = {
                code
                for code, count in current_counts.items()
                if count >= MINIMUM_CELL_N
                and code in reference
                and reference[code]["coordinates_available"].casefold() == "true"
            }
            actual_codes = {row["Código DEIS"] for row in rows}
            if not rows:
                failures.append(
                    {"check": "zero_publishable_markers", "context": name, "period": period_name}
                )
            if actual_codes != expected_codes:
                failures.append(
                    {
                        "check": "suppression_or_mapping_mismatch",
                        "context": name,
                        "period": period_name,
                        "expected": sorted(expected_codes),
                        "actual": sorted(actual_codes),
                    }
                )
            if any(
                row["Episodios"] < MINIMUM_CELL_N
                or row["Código DEIS"] == HEC_DEIS_CODE
                or not math.isfinite(float(row["Latitud"]))
                or not math.isfinite(float(row["Longitud"]))
                or (row["Latitud"], row["Longitud"]) == (0.0, 0.0)
                for row in rows
            ):
                failures.append(
                    {"check": "invalid_or_suppressed_marker", "context": name, "period": period_name}
                )
            for row in rows:
                code = row["Código DEIS"]
                prior_count = previous_counts[code]
                if prior_count < MINIMUM_CELL_N and row["Variación"] is not None:
                    failures.append(
                        {"check": "suppressed_comparison_exposed", "context": name, "period": period_name, "code": code}
                    )
                if prior_count >= MINIMUM_CELL_N and row["Variación"] != row["Episodios"] - prior_count:
                    failures.append(
                        {"check": "comparison_variation", "context": name, "period": period_name, "code": code}
                    )
            visible_fields = {key.casefold() for row in rows for key in row}
            if any(
                fragment in field_name
                for field_name in visible_fields
                for fragment in FORBIDDEN_VISIBLE_FRAGMENTS
            ):
                failures.append(
                    {"check": "identity_field_exposed", "context": name, "period": period_name}
                )
            public_rows = [
                {key: value for key, value in row.items() if key not in {"Latitud", "Longitud"}}
                for row in rows
            ]
            parsed_csv = list(
                csv.DictReader(
                    StringIO(rows_to_csv(public_rows).decode("utf-8-sig"))
                )
            )
            mapped_total = sum(row["Episodios"] for row in rows)
            if (
                mapped_total != summary["publishable_referrals"]
                or len(parsed_csv) != len(public_rows)
                or sum(int(row["Episodios"]) for row in parsed_csv) != mapped_total
            ):
                failures.append(
                    {"check": "map_table_csv_reconciliation", "context": name, "period": period_name}
                )
            expected_source = (
                "CIRUGIAS"
                if context["role_id"] in {"service_chief_surgical", "professional_surgical"}
                else "DERIVACIONES"
                if context["role_id"] == "service_chief_clinical"
                and context.get("service_id")
                and context.get("specialty_id") is None
                and not specialty_choices(context["service_id"], repo_root)
                else "LISTA_ESPERA_AMB"
            )
            if summary["source"] != expected_source:
                failures.append(
                    {"check": "role_scope_source", "context": name, "period": period_name, "expected": expected_source, "actual": summary["source"]}
                )
            if context.get("service_id") and any(
                row["service_id"] != context["service_id"] for row in raw
            ):
                failures.append({"check": "service_scope_leak", "context": name})
            if context.get("specialty_id") and any(
                row.get("specialty_id") != context["specialty_id"] for row in raw
            ):
                failures.append({"check": "specialty_scope_leak", "context": name})
            signature = territorial_map_signature(
                summary, dataset, current, previous, context
            )
            if len(signature) != 64:
                failures.append({"check": "map_signature", "context": name})
            if summary["source"] == "LISTA_ESPERA_AMB" and rows:
                center = rows[0]["Código DEIS"]
                specialty_breakdown = referring_center_specialties(
                    dataset, current, previous, context, center
                )
                diagnosis_breakdown = referring_center_diagnoses(
                    dataset, current, context, center
                )
                prestation_breakdown = referring_center_prestations(
                    dataset, current, context, center
                )
                queue_breakdown = center_waitlist_context(
                    dataset, current, context, center
                )
                nested_counts = [
                    *[row["Actual"] for row in specialty_breakdown],
                    *[row["Episodios"] for row in diagnosis_breakdown],
                    *[row["Episodios"] for row in prestation_breakdown],
                    *[row["Total"] for row in queue_breakdown],
                    *[
                        row["Abiertos"]
                        for row in queue_breakdown
                        if row["Abiertos"] is not None
                    ],
                ]
                if any(count < MINIMUM_CELL_N for count in nested_counts):
                    failures.append(
                        {"check": "suppressed_drilldown_exposed", "context": name, "period": period_name, "center": center}
                    )
                center_total = rows[0]["Episodios"]
                if any(
                    sum(group) > center_total
                    for group in (
                        [row["Actual"] for row in specialty_breakdown],
                        [row["Episodios"] for row in diagnosis_breakdown],
                        [row["Episodios"] for row in prestation_breakdown],
                        [row["Total"] for row in queue_breakdown],
                    )
                ):
                    failures.append(
                        {"check": "drilldown_reconciliation", "context": name, "period": period_name, "center": center}
                    )
            if "SIM-PROF-M-" in name:
                mixed_signatures[(period_name, context["professional_lens"])] = _data_signature(summary["source"], rows)
            marker_counts.append(len(rows))
            summaries.append(
                {
                    "context": name,
                    "period": period_name,
                    "source": summary["source"],
                    "aggregation_level": summary["aggregation_level"],
                    "markers": len(rows),
                    "published_episodes": mapped_total,
                    "suppressed_cells": summary["suppressed_cell_count"],
                    "map_signature": signature,
                }
            )

    # Materially different effective scopes must not collapse to one aggregate.
    data_signature_scopes: dict[tuple, set[tuple]] = defaultdict(set)
    for item in contexts:
        context = item["context"]
        current, previous = PERIODS["Q2"]
        summary = territorial_scope_summary(dataset, current, previous, context)
        raw = _raw_scope_rows(dataset, current, context, summary["source"])
        data_signature_scopes[_data_signature(summary["source"], summary["rows"])].add(
            _effective_scope(summary["source"], raw)
        )
    for signature, effective_scopes in data_signature_scopes.items():
        if len(effective_scopes) > 1:
            failures.append(
                {"check": "identical_material_scopes", "scope_count": len(effective_scopes), "signature": str(signature)[:240]}
            )

    for period_name in PERIODS:
        if mixed_signatures.get((period_name, "clinical")) == mixed_signatures.get((period_name, "surgical")):
            failures.append({"check": "mixed_lenses_not_independent", "period": period_name})

    # Supported clinical filters must change signatures whenever both results publish.
    clinical_specialties = [
        item
        for item in load_contract("services", repo_root)["analytical_specialties"]
        if item.get("mvp_enabled") and item["dashboard_type"] == "clinical"
    ]
    filter_signature_checks = 0
    for specialty in clinical_specialties:
        base_context = {
            "role_id": "service_chief_clinical",
            "service_id": specialty["parent_unit_id"],
            "specialty_id": specialty["specialty_id"],
        }
        current, previous = PERIODS["Q2"]
        raw = scoped_network_rows(dataset, current, base_context)
        prestations = sorted({row["requested_prestation"] for row in raw})
        prestation_signatures = []
        for prestation in prestations:
            context = {**base_context, "prestation_type": prestation}
            summary = territorial_scope_summary(dataset, current, previous, context)
            if summary["rows"]:
                prestation_signatures.append(_data_signature(summary["source"], summary["rows"]))
        if len(prestation_signatures) >= 2:
            filter_signature_checks += 1
            if len(set(prestation_signatures)) != len(prestation_signatures):
                failures.append({"check": "prestation_filter_signature", "specialty": specialty["specialty_id"]})
        diagnoses = diagnosis_options(raw, repo_root=repo_root)
        diagnosis_signatures = []
        for diagnosis in diagnoses:
            context = {
                **base_context,
                "referral_diagnosis_id": diagnosis["diagnosis_group_id"],
            }
            summary = territorial_scope_summary(dataset, current, previous, context)
            if summary["rows"]:
                diagnosis_signatures.append(_data_signature(summary["source"], summary["rows"]))
        if len(diagnosis_signatures) >= 2:
            filter_signature_checks += 1
            if len(set(diagnosis_signatures)) != len(diagnosis_signatures):
                failures.append({"check": "diagnosis_filter_signature", "specialty": specialty["specialty_id"]})
        overview = territorial_scope_summary(dataset, current, previous, base_context)
        if len(overview["rows"]) >= 2:
            first_context = {**base_context, "selected_center_code": overview["rows"][0]["Código DEIS"]}
            second_context = {**base_context, "selected_center_code": overview["rows"][1]["Código DEIS"]}
            if territorial_map_signature(overview, dataset, current, previous, first_context) == territorial_map_signature(overview, dataset, current, previous, second_context):
                failures.append({"check": "referring_center_signature", "specialty": specialty["specialty_id"]})
            filter_signature_checks += 1

    # Every surgical specialty/procedure filter has publishable deterministic coverage.
    specialty_catalog = load_contract("services", repo_root)["analytical_specialties"]
    surgical_specialties = [
        item for item in specialty_catalog if item.get("mvp_enabled") and item["dashboard_type"] == "surgical"
    ]
    procedure_checks = 0
    for specialty in surgical_specialties:
        base_context = {
            "role_id": "service_chief_surgical",
            "service_id": specialty["parent_unit_id"],
            "specialty_id": specialty["specialty_id"],
        }
        for period_name, (current, previous) in PERIODS.items():
            options = surgical_procedure_options(dataset, current, base_context)
            procedure_signatures = set()
            for option in options:
                context = {**base_context, "procedure_code": option["procedure_code"]}
                summary = territorial_scope_summary(dataset, current, previous, context)
                procedure_checks += 1
                if not summary["rows"]:
                    failures.append({"check": "procedure_zero_markers", "specialty": specialty["specialty_id"], "procedure": option["procedure_code"], "period": period_name})
                procedure_signatures.add(_data_signature(summary["source"], summary["rows"]))
            if len(procedure_signatures) != len(options):
                failures.append({"check": "procedure_filter_signature", "specialty": specialty["specialty_id"], "period": period_name})

    palliative_specialties = specialty_choices(
        "alivio_dolor_cuidados_paliativos", repo_root
    )
    if palliative_specialties:
        failures.append({"check": "fabricated_palliative_specialty"})

    first_generation = generate_dataset()
    second_generation = generate_dataset()
    generation_byte_equivalent = (
        json.dumps(first_generation, ensure_ascii=False, sort_keys=True).encode("utf-8")
        == json.dumps(second_generation, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )
    if not generation_byte_equivalent:
        failures.append({"check": "deterministic_generation"})

    return {
        "status": "PASS" if not failures else "FAIL",
        "dataset_id": dataset.metadata.get("dataset_id"),
        "contract_version": dataset.metadata.get("contract_version"),
        "minimum_geographic_cell_n": MINIMUM_CELL_N,
        "default_contexts": len(contexts),
        "period_contexts": len(summaries),
        "procedure_period_contexts": procedure_checks,
        "filter_signature_checks": filter_signature_checks,
        "minimum_publishable_markers": min(marker_counts, default=0),
        "maximum_publishable_markers": max(marker_counts, default=0),
        "deterministic_generation": generation_byte_equivalent,
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
        f"{result['status']} territorial coverage: "
        f"contexts={result['default_contexts']}; "
        f"period_contexts={result['period_contexts']}; "
        f"procedure_checks={result['procedure_period_contexts']}; "
        f"minimum_markers={result['minimum_publishable_markers']}; "
        f"failures={len(result['failures'])}; "
        f"elapsed={result['elapsed_seconds']}s"
    )
    if result["failures"]:
        print(json.dumps(result["failures"][:20], ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
