#!/usr/bin/env python3
"""Independent closure audit for the uncommitted Day 5 candidate."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from time import perf_counter


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_simulated_data import generate_dataset  # noqa: E402
from hec_dashboard.app_config import load_contract  # noqa: E402
from hec_dashboard.data_ingestion import CandidateDataset, validate_tables, validate_workbook  # noqa: E402
from hec_dashboard.indicator_engine import IndicatorContext, IndicatorEngine  # noqa: E402
from hec_dashboard.visual_analytics import (  # noqa: E402
    aging_distribution,
    origin_bubbles,
    prestation_composition,
    role_activity_composition,
    role_activity_trend,
    scoped_waitlist_rows,
    status_flow,
    waitlist_indicator_trend,
)
from validate_data_contract import load_simulated_tables  # noqa: E402


WAITLIST_IDS = (
    "new_waitlist_open_count",
    "new_wait_median_days",
    "new_wait_p75_days",
    "new_wait_over_90_pct",
    "new_waitlist_resolution_pct",
    "followup_overdue_open_count",
    "followup_overdue_median_days",
    "followup_overdue_p75_days",
    "followup_unscheduled_pct",
    "followup_resolution_pct",
)
Q1 = (date(2026, 1, 1), date(2026, 3, 31))
Q2 = (date(2026, 4, 1), date(2026, 6, 30))


def audit(repo_root: Path) -> dict[str, object]:
    started = perf_counter()
    failures: list[dict[str, object]] = []
    report = validate_tables(
        load_simulated_tables(repo_root),
        repo_root,
        validation_timestamp_utc="2026-09-02T12:00:00+00:00",
    )
    workbook_report = validate_workbook(
        repo_root / "templates" / "plantilla_carga_hec_1_3.xlsx", repo_root
    )
    if not report.activatable or report.rejected_row_count:
        failures.append({"check": "packaged_data", "summary": report.summary()})
    if not workbook_report.activatable or workbook_report.rejected_row_count:
        failures.append(
            {"check": "workbook", "summary": workbook_report.summary()}
        )
    dataset = CandidateDataset(report.metadata, report.accepted_rows, report.summary())
    engine = IndicatorEngine.from_repo(repo_root)
    scopes = sorted(
        {
            (row["service_id"], row["specialty_id"])
            for row in dataset.tables.get("LISTA_ESPERA_AMB", [])
        }
    )
    indicator_checks = 0
    for service_id, specialty_id in scopes:
        for current, previous in ((Q1, Q2), (Q2, Q1)):
            context = IndicatorContext(
                period_start=current[0],
                period_end=current[1],
                previous_period_start=previous[0],
                previous_period_end=previous[1],
                indicator_profile="institutional",
                service_id=service_id,
                specialty_id=specialty_id,
            )
            for indicator_id in WAITLIST_IDS:
                result = engine.calculate(indicator_id, dataset, context)
                indicator_checks += 1
                if result.status != "available":
                    failures.append(
                        {
                            "check": "specialty_indicator",
                            "scope": [service_id, specialty_id],
                            "indicator_id": indicator_id,
                            "status": result.status,
                            "valid_n": result.valid_n,
                        }
                    )
    professional_checks = 0
    for profile in load_contract("professional_profiles", repo_root)["profiles"]:
        profile_type = (
            "professional_surgical"
            if profile["profile_type"] == "surgical"
            else "professional_clinical"
        )
        for current, previous in ((Q1, Q2), (Q2, Q1)):
            context = IndicatorContext(
                period_start=current[0],
                period_end=current[1],
                previous_period_start=previous[0],
                previous_period_end=previous[1],
                indicator_profile=profile_type,
                service_id=profile["service_id"],
                specialty_id=profile["specialty_id"],
                simulated_profile_key=profile["professional_id"],
            )
            for indicator_id in WAITLIST_IDS[5:]:
                result = engine.calculate(indicator_id, dataset, context)
                professional_checks += 1
                if result.status != "available":
                    failures.append(
                        {
                            "check": "professional_followup",
                            "profile": profile["professional_id"],
                            "indicator_id": indicator_id,
                            "status": result.status,
                            "valid_n": result.valid_n,
                        }
                    )
    director_context = {"role_id": "director"}
    map_rows = origin_bubbles(dataset, Q2, Q1, director_context, repo_root=repo_root)
    mapped_total = sum(row["Episodios"] for row in map_rows)
    scoped_total = len(scoped_waitlist_rows(dataset, Q2, director_context))
    if mapped_total != scoped_total:
        failures.append(
            {
                "check": "map_reconciliation",
                "mapped": mapped_total,
                "scoped": scoped_total,
            }
        )
    chart_checks = 0
    current_rows = scoped_waitlist_rows(dataset, Q2, director_context)
    reconciliations = {
        "status_flow": (sum(row["Episodios"] for row in status_flow(current_rows)), len(current_rows)),
        "aging": (
            sum(row["Episodios"] for row in aging_distribution(current_rows)),
            sum(row["episode_status"].startswith("open_") for row in current_rows),
        ),
        "prestation": (sum(row["Episodios"] for row in prestation_composition(current_rows)), len(current_rows)),
    }
    for name, (actual, expected) in reconciliations.items():
        chart_checks += 1
        if actual != expected:
            failures.append({"check": f"chart_{name}", "actual": actual, "expected": expected})
    referral_rows = [
        row
        for row in dataset.tables["DERIVACIONES"]
        if Q2[0] <= row["period_date"] <= Q2[1]
    ]
    composition_total = sum(
        row["Eventos"]
        for row in role_activity_composition(dataset, Q2, director_context)
    )
    chart_checks += 1
    if composition_total != len(referral_rows):
        failures.append(
            {"check": "chart_role_composition", "actual": composition_total, "expected": len(referral_rows)}
        )
    governed_trend = waitlist_indicator_trend(dataset, Q2, Q1, director_context)
    chart_checks += 1
    if len(governed_trend) != 8 or any(row["Estado"] != "available" for row in governed_trend):
        failures.append({"check": "chart_governed_waitlist_trend", "rows": governed_trend})
    activity_trend = role_activity_trend(dataset, Q2, Q1, director_context)
    chart_checks += 1
    if not activity_trend:
        failures.append({"check": "chart_role_activity_trend"})

    mixed_profile = next(
        profile
        for profile in load_contract("professional_profiles", repo_root)["profiles"]
        if profile["profile_type"] == "mixed"
    )
    mixed_rows = [
        row
        for row in dataset.tables["ACTIVIDAD_PROF"]
        if row["simulated_profile_key"] == mixed_profile["professional_id"]
    ]
    clinical_ids = {row["activity_id"] for row in mixed_rows if row["lens"] == "clinical"}
    surgical_ids = {row["activity_id"] for row in mixed_rows if row["lens"] == "surgical"}
    if not clinical_ids or not surgical_ids or clinical_ids & surgical_ids:
        failures.append({"check": "mixed_lens_isolation"})
    first_tables, first_metadata = generate_dataset()
    second_tables, second_metadata = generate_dataset()
    if first_tables != second_tables or first_metadata != second_metadata:
        failures.append({"check": "determinism"})
    forbidden = {
        "patient_id",
        "rut",
        "patient_name",
        "patient_address",
        "employee_id",
    }
    waitlist_columns = set(first_tables["LISTA_ESPERA_AMB"][0])
    if forbidden & waitlist_columns:
        failures.append(
            {"check": "privacy_columns", "found": sorted(forbidden & waitlist_columns)}
        )
    elapsed = perf_counter() - started
    if elapsed >= 5:
        failures.append({"check": "performance", "elapsed_seconds": elapsed})
    return {
        "status": "PASS" if not failures else "FAIL",
        "dataset_id": report.metadata.get("dataset_id"),
        "contract_version": report.metadata.get("contract_version"),
        "accepted_rows": report.accepted_row_count,
        "waitlist_rows": len(dataset.tables.get("LISTA_ESPERA_AMB", [])),
        "specialty_period_contexts": len(scopes) * 2,
        "professional_period_contexts": 27 * 2,
        "indicator_checks": indicator_checks,
        "professional_checks": professional_checks,
        "map_cells": len(map_rows),
        "map_reconciled_rows": mapped_total,
        "chart_reconciliation_checks": chart_checks,
        "mixed_lens_rows": {"clinical": len(clinical_ids), "surgical": len(surgical_ids)},
        "failure_count": len(failures),
        "failures": failures,
        "elapsed_seconds": round(elapsed, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "reports" / "day5_candidate_audit.json",
    )
    args = parser.parse_args()
    result = audit(REPO_ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{result['status']} Day 5: accepted={result['accepted_rows']}; "
        f"waitlist={result['waitlist_rows']}; indicators={result['indicator_checks']}; "
        f"professional={result['professional_checks']}; maps={result['map_cells']}; "
        f"charts={result['chart_reconciliation_checks']}; "
        f"failures={result['failure_count']}; elapsed={result['elapsed_seconds']}s"
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
