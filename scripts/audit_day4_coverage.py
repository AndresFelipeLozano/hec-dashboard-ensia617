#!/usr/bin/env python3
"""Audit bundled Day 4 role, service, specialty, profile, and lens coverage."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from calculate_indicators import load_packaged_candidate  # noqa: E402
from hec_dashboard.app_config import (  # noqa: E402
    get_professional_profile,
    get_role_definition,
    primary_indicator_ids,
    professional_lens_context,
    professional_profiles,
    service_choices,
    specialty_choices,
)
from hec_dashboard.indicator_engine import (  # noqa: E402
    IndicatorContext,
    IndicatorEngine,
)


Q1 = (date(2026, 1, 1), date(2026, 3, 31))
Q2 = (date(2026, 4, 1), date(2026, 6, 30))
BAD_ACTIVE_STATUSES = {"insufficient_n", "zero_denominator", "not_applicable"}


@dataclass(frozen=True)
class SupportedContext:
    role_id: str
    calculation_role_id: str
    service_id: str | None = None
    specialty_id: str | None = None
    simulated_profile_key: str | None = None
    professional_lens: str | None = None
    professional_type: str | None = None


@dataclass(frozen=True)
class AuditRecord:
    role_id: str
    service_id: str | None
    specialty_id: str | None
    simulated_profile_key: str | None
    professional_lens: str | None
    evaluated_period: str
    current_period: str
    comparison_period: str
    indicator_id: str
    binding_availability: str
    status: str
    valid_n: int
    required_n: int


def supported_contexts(dataset) -> list[SupportedContext]:
    del dataset
    contexts = [
        SupportedContext("director", "director"),
        SupportedContext("medical_director", "medical_director"),
    ]
    for dashboard_type, role_id in (
        ("clinical", "service_chief_clinical"),
        ("surgical", "service_chief_surgical"),
    ):
        for service in service_choices(dashboard_type):
            service_id = service["unit_id"]
            contexts.append(
                SupportedContext(role_id, role_id, service_id=service_id)
            )
            for specialty in specialty_choices(service_id):
                contexts.append(
                    SupportedContext(
                        role_id,
                        role_id,
                        service_id=service_id,
                        specialty_id=specialty["specialty_id"],
                    )
                )
    for profile in professional_profiles("clinical"):
        scope = professional_lens_context(profile, "clinical")
        contexts.append(
            SupportedContext(
                "professional_clinical",
                "professional_clinical",
                service_id=scope["service_id"],
                specialty_id=scope["specialty_id"],
                simulated_profile_key=profile["professional_id"],
                professional_lens="clinical",
                professional_type="clinical",
            )
        )
    for profile in professional_profiles("surgical"):
        scope = professional_lens_context(profile, "surgical")
        contexts.append(
            SupportedContext(
                "professional_surgical",
                "professional_surgical",
                service_id=scope["service_id"],
                specialty_id=scope["specialty_id"],
                simulated_profile_key=profile["professional_id"],
                professional_lens="surgical",
                professional_type="surgical",
            )
        )
    for profile in professional_profiles("mixed"):
        for lens, calculation_role_id in (
            ("clinical", "professional_clinical"),
            ("surgical", "professional_surgical"),
        ):
            scope = professional_lens_context(profile, lens)
            contexts.append(
                SupportedContext(
                    "professional_mixed",
                    calculation_role_id,
                    service_id=scope["service_id"],
                    specialty_id=scope["specialty_id"],
                    simulated_profile_key=profile["professional_id"],
                    professional_lens=lens,
                    professional_type="mixed",
                )
            )
    return contexts


def _indicator_context(
    supported: SupportedContext,
    period: tuple[date, date],
) -> IndicatorContext:
    role = get_role_definition(supported.calculation_role_id)
    return IndicatorContext(
        period_start=period[0],
        period_end=period[1],
        previous_period_start=period[0],
        previous_period_end=period[1],
        indicator_profile=role["indicator_profile"],
        professional_lens=supported.professional_lens,
        service_id=supported.service_id,
        specialty_id=supported.specialty_id,
        simulated_profile_key=supported.simulated_profile_key,
    )


def audit_coverage(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    started = perf_counter()
    dataset = load_packaged_candidate(repo_root)
    engine = IndicatorEngine.from_repo(repo_root)
    ui_contract = json.loads(
        (repo_root / "config" / "ui_contract.json").read_text(encoding="utf-8")
    )
    mixed_view_contract = next(
        item
        for item in ui_contract["view_contracts"]
        if item["role_id"] == "professional_mixed"
    )
    binding_by_id = engine.bindings
    records: list[AuditRecord] = []
    failures: list[AuditRecord] = []
    integrity_failures: list[dict[str, Any]] = []
    mixed_profile_results: list[dict[str, Any]] = []
    context_counts: Counter[str] = Counter()
    status_by_role: dict[str, Counter[str]] = defaultdict(Counter)
    contexts = supported_contexts(dataset)
    for profile in professional_profiles("mixed"):
        professional_id = profile["professional_id"]
        lens_scopes = {
            lens: professional_lens_context(profile, lens)
            for lens in ("clinical", "surgical")
        }
        shared_fields = ("service_id", "specialty_id", "specialty_display_name")
        if (
            profile.get("specialty_id") != "cirugia_pediatrica"
            or profile.get("service_id") != "cirugia_infantil"
            or any(
                lens_scopes[lens].get(field) != profile.get(field)
                for lens in ("clinical", "surgical")
                for field in shared_fields
            )
        ):
            integrity_failures.append(
                {
                    "professional_id": professional_id,
                    "reason": "mixed_profile_must_preserve_pediatric_surgery_scope",
                }
            )
        profile_rows = [
            row
            for row in dataset.tables["ACTIVIDAD_PROF"]
            if row["simulated_profile_key"] == professional_id
        ]
        ids_by_lens = {
            lens: {
                row["activity_id"] for row in profile_rows if row["lens"] == lens
            }
            for lens in ("clinical", "surgical")
        }
        duplicated_ids = sorted(ids_by_lens["clinical"] & ids_by_lens["surgical"])
        if duplicated_ids:
            integrity_failures.append(
                {
                    "professional_id": professional_id,
                    "reason": "mixed_lens_activity_ids_overlap",
                    "activity_ids": duplicated_ids[:10],
                }
            )
        for lens, activity_prefix, activity_class in (
            ("clinical", ("CONS-", "TELECONS"), "outpatient_clinical"),
            ("surgical", ("PROC-",), "surgical_procedural"),
        ):
            scope = lens_scopes[lens]
            if scope.get("activity_class") != activity_class:
                integrity_failures.append(
                    {
                        "professional_id": professional_id,
                        "lens": lens,
                        "reason": "mixed_activity_class_mismatch",
                    }
                )
            for period_label, period in (("Q1", Q1), ("Q2", Q2)):
                rows = [
                    row
                    for row in profile_rows
                    if row["lens"] == lens
                    and period[0] <= row["period_date"] <= period[1]
                ]
                incompatible = [
                    row["activity_id"]
                    for row in rows
                    if row["profile_type"] != "mixed"
                    or row["service_id"] != profile["service_id"]
                    or row["specialty_id"] != profile["specialty_id"]
                    or not row["activity_code"].startswith(activity_prefix)
                ]
                mixed_profile_results.append(
                    {
                        "professional_id": professional_id,
                        "specialty_id": profile["specialty_id"],
                        "service_id": profile["service_id"],
                        "lens": lens,
                        "period": period_label,
                        "row_count": len(rows),
                        "incompatible_activity_ids": incompatible[:10],
                    }
                )
                if len(rows) != 60 or incompatible:
                    integrity_failures.append(
                        {
                            "professional_id": professional_id,
                            "lens": lens,
                            "period": period_label,
                            "reason": "mixed_lens_period_integrity_failure",
                            "row_count": len(rows),
                            "incompatible_activity_ids": incompatible[:10],
                        }
                    )
    for supported in contexts:
        context_counts[supported.role_id] += 1
        if supported.simulated_profile_key:
            profile = get_professional_profile(supported.simulated_profile_key)
            rows = [
                row
                for row in dataset.tables["ACTIVIDAD_PROF"]
                if row["simulated_profile_key"] == supported.simulated_profile_key
                and row["lens"] == supported.professional_lens
            ]
            incompatible = [
                row["activity_id"]
                for row in rows
                if row["profile_type"] != supported.professional_type
                or row["service_id"] != supported.service_id
                or row["specialty_id"] != supported.specialty_id
            ]
            if not profile.get("specialty_id") or not rows or incompatible:
                integrity_failures.append(
                    {
                        "professional_id": supported.simulated_profile_key,
                        "lens": supported.professional_lens,
                        "specialty_id": supported.specialty_id,
                        "row_count": len(rows),
                        "incompatible_activity_ids": incompatible[:10],
                    }
                )
        for period_label, period in (("current", Q2), ("comparison", Q1)):
            indicator_context = _indicator_context(supported, period)
            for indicator_id in primary_indicator_ids(
                supported.calculation_role_id, repo_root
            ):
                result = engine.calculate(indicator_id, dataset, indicator_context)
                availability = binding_by_id[indicator_id]["availability"]
                record = AuditRecord(
                    role_id=supported.role_id,
                    service_id=supported.service_id,
                    specialty_id=supported.specialty_id,
                    simulated_profile_key=supported.simulated_profile_key,
                    professional_lens=supported.professional_lens,
                    evaluated_period=period_label,
                    current_period="2026-04-01/2026-06-30",
                    comparison_period="2026-01-01/2026-03-31",
                    indicator_id=indicator_id,
                    binding_availability=availability,
                    status=result.status,
                    valid_n=result.valid_n,
                    required_n=result.minimum_valid_n,
                )
                records.append(record)
                status_by_role[supported.role_id][result.status] += 1
                required_filters = {
                    "simulated_profile_key": supported.simulated_profile_key,
                    "professional_lens": supported.professional_lens,
                    "specialty_id": supported.specialty_id,
                    "service_id": supported.service_id,
                }
                if supported.simulated_profile_key and any(
                    result.filters.get(key) != value
                    for key, value in required_filters.items()
                ):
                    integrity_failures.append(
                        {
                            "professional_id": supported.simulated_profile_key,
                            "indicator_id": indicator_id,
                            "reason": "result_filter_scope_mismatch",
                        }
                    )
                if availability == "active" and result.status in BAD_ACTIVE_STATUSES:
                    failures.append(record)

    mixed_composite_result_count = sum(
        record.role_id == "professional_mixed"
        and record.professional_lens is None
        for record in records
    )
    if (
        mixed_composite_result_count
        or mixed_view_contract["primary_indicator_ids"]
        or mixed_view_contract["combined_performance_score_allowed"] is not False
    ):
        integrity_failures.append(
            {
                "reason": "mixed_composite_result_is_not_allowed",
                "composite_result_count": mixed_composite_result_count,
            }
        )

    audit_period_by_quarter = {"Q1": "comparison", "Q2": "current"}
    for summary in mixed_profile_results:
        statuses = Counter(
            record.status
            for record in records
            if record.role_id == "professional_mixed"
            and record.simulated_profile_key == summary["professional_id"]
            and record.professional_lens == summary["lens"]
            and record.evaluated_period == audit_period_by_quarter[summary["period"]]
        )
        summary["indicator_status_counts"] = dict(sorted(statuses.items()))

    return {
        "dataset_id": dataset.metadata["dataset_id"],
        "accepted_rows": dataset.validation_summary["accepted_rows"],
        "context_count": len(contexts),
        "record_count": len(records),
        "context_counts_by_role": dict(sorted(context_counts.items())),
        "status_counts_by_role": {
            role: dict(sorted(counts.items()))
            for role, counts in sorted(status_by_role.items())
        },
        "failure_count": len(failures) + len(integrity_failures),
        "failures": [asdict(record) for record in failures],
        "integrity_failures": integrity_failures,
        "mixed_profile_results": mixed_profile_results,
        "mixed_composite_result_count": mixed_composite_result_count,
        "records": [asdict(record) for record in records],
        "elapsed_seconds": round(perf_counter() - started, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_coverage(REPO_ROOT)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        "PASS" if report["failure_count"] == 0 else "FAIL",
        "coverage:",
        f"dataset={report['dataset_id']};",
        f"accepted={report['accepted_rows']};",
        f"contexts={report['context_count']};",
        f"checks={report['record_count']};",
        f"failures={report['failure_count']};",
        f"elapsed={report['elapsed_seconds']:.4f}s",
    )
    for role_id, counts in report["status_counts_by_role"].items():
        summary = ", ".join(f"{key}={value}" for key, value in counts.items())
        print(f"  {role_id}: {summary}")
    for mixed in report["mixed_profile_results"]:
        statuses = ", ".join(
            f"{key}={value}"
            for key, value in mixed["indicator_status_counts"].items()
        )
        print(
            "  mixed",
            f"{mixed['period']} {mixed['lens']}:",
            f"rows={mixed['row_count']};",
            f"specialty={mixed['specialty_id']};",
            statuses,
        )
    if report["failures"]:
        for failure in report["failures"][:20]:
            print("  FAILURE", json.dumps(failure, ensure_ascii=False))
    if report["integrity_failures"]:
        for failure in report["integrity_failures"][:20]:
            print("  INTEGRITY FAILURE", json.dumps(failure, ensure_ascii=False))
    if report["failure_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
