#!/usr/bin/env python3
"""Generate the deterministic Day 3 indicator snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from hec_dashboard.data_ingestion import CandidateDataset, validate_tables  # noqa: E402
from hec_dashboard.indicator_engine import (  # noqa: E402
    IndicatorContext,
    IndicatorEngine,
)
from validate_data_contract import load_simulated_tables  # noqa: E402


def load_packaged_candidate(repo_root: Path) -> CandidateDataset:
    report = validate_tables(
        load_simulated_tables(repo_root),
        repo_root,
        validation_timestamp_utc="2026-09-02T12:00:00+00:00",
    )
    if not report.activatable or report.rejected_row_count:
        raise ValueError(
            "Packaged simulated data must be fully valid before calculation"
        )
    return CandidateDataset(
        metadata=report.metadata,
        tables=report.accepted_rows,
        validation_summary=report.summary(),
    )


def build_snapshot(repo_root: Path) -> dict[str, object]:
    dataset = load_packaged_candidate(repo_root)
    engine = IndicatorEngine.from_repo(repo_root)
    context = IndicatorContext(
        period_start=date(2026, 4, 1),
        period_end=date(2026, 6, 30),
        previous_period_start=date(2026, 1, 1),
        previous_period_end=date(2026, 3, 31),
    )
    results = [result.as_dict() for result in engine.calculate_all(dataset, context)]
    status_counts: dict[str, int] = {}
    for result in results:
        status = result["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "snapshot_version": "1.1.0",
        "generated_at_utc": "2026-09-02T15:00:00Z",
        "dataset_id": dataset.metadata["dataset_id"],
        "contract_version": dataset.metadata["contract_version"],
        "indicator_catalog_version": engine.catalog["catalog_version"],
        "binding_version": engine.binding_contract["binding_version"],
        "context": {
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
            "previous_period_start": "2026-01-01",
            "previous_period_end": "2026-03-31",
            "filters": {},
        },
        "result_count": len(results),
        "status_counts": status_counts,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data" / "derived" / "indicator_snapshot.json",
    )
    args = parser.parse_args()
    try:
        snapshot = build_snapshot(REPO_ROOT)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL indicator calculation: {exc}", file=sys.stderr)
        return 1
    counts = ", ".join(
        f"{status}={count}"
        for status, count in sorted(snapshot["status_counts"].items())
    )
    print(
        f"PASS indicators: {snapshot['result_count']} results; {counts}; "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
