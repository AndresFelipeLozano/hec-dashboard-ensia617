#!/usr/bin/env python3
"""Validate the Day 2 contract, packaged reference, and simulated dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hec_dashboard.data_ingestion import validate_tables, validate_workbook  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_simulated_tables(repo_root: Path) -> dict[str, list[list[str]]]:
    mapping = {
        "DERIVACIONES": "derivaciones_simuladas.csv",
        "CIRUGIAS": "cirugias_simuladas.csv",
        "ACTIVIDAD_PROF": "actividad_profesional_simulada.csv",
        "LISTA_ESPERA_AMB": "lista_espera_ambulatoria_simulada.csv",
    }
    metadata = json.loads(
        (repo_root / "data" / "simulated" / "metadata.json").read_text()
    )
    contract = json.loads((repo_root / "config" / "data_contract.json").read_text())
    allowed_keys = [item["key"] for item in contract["metadata_keys"]]
    tables: dict[str, list[list[str]]] = {
        "METADATOS": [["clave", "valor"]]
        + [[key, str(metadata[key])] for key in allowed_keys]
    }
    for sheet, filename in mapping.items():
        with (
            repo_root / "data" / "simulated" / filename
        ).open("r", encoding="utf-8", newline="") as handle:
            tables[sheet] = list(csv.reader(handle))
    return tables


def validate_snapshot(repo_root: Path) -> dict[str, int]:
    manifest_path = repo_root / "data" / "reference" / "deis_snapshot_manifest.json"
    snapshot_path = (
        repo_root / "data" / "reference" / "deis_establishments_ssmc_snapshot.csv"
    )
    manifest = json.loads(manifest_path.read_text())
    errors: list[str] = []
    if sha256(snapshot_path) != manifest["output_sha256"]:
        errors.append("DEIS snapshot SHA-256 does not match its manifest")
    with snapshot_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    codes = [row["establishment_code"] for row in rows]
    if len(codes) != len(set(codes)):
        errors.append("DEIS snapshot contains duplicate establishment codes")
    for index, row in enumerate(rows, start=2):
        try:
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])
        except ValueError:
            errors.append(f"DEIS snapshot row {index}: invalid coordinates")
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            errors.append(f"DEIS snapshot row {index}: coordinates out of range")
    if len(rows) != manifest["rows"]:
        errors.append("DEIS snapshot row count does not match its manifest")
    if manifest["upstream_validation"]["fail"] != 0:
        errors.append("DEIS upstream ETL manifest contains blocking failures")
    if errors:
        raise ValueError("\n".join(errors))
    return {"rows": len(rows), "codes": len(set(codes))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path)
    args = parser.parse_args()
    try:
        snapshot_counts = validate_snapshot(REPO_ROOT)
        report = validate_tables(
            load_simulated_tables(REPO_ROOT),
            REPO_ROOT,
            validation_timestamp_utc="2026-09-02T12:00:00+00:00",
        )
        if not report.activatable:
            details = [
                issue.message
                for issue in report.structural_errors + report.issues[:20]
            ]
            raise ValueError(
                "Packaged simulated data is not activatable:\n" + "\n".join(details)
            )
        if report.rejected_row_count:
            raise ValueError(
                f"Packaged simulated data quarantined {report.rejected_row_count} rows"
            )
        print(
            "PASS data contract: "
            f"{report.accepted_row_count} accepted rows; "
            f"{report.accepted_record_pct:.2f}% acceptance; "
            f"{snapshot_counts['rows']} DEIS reference rows"
        )
        for sheet, rows in report.accepted_rows.items():
            print(f"PASS {sheet}: {len(rows)} accepted; 0 quarantined")
        if args.workbook:
            workbook_report = validate_workbook(args.workbook, REPO_ROOT)
            if not workbook_report.activatable or workbook_report.rejected_row_count:
                raise ValueError(
                    "Workbook failed validation: "
                    + json.dumps(workbook_report.summary(), ensure_ascii=False)
                )
            print(
                "PASS workbook: "
                f"{workbook_report.accepted_row_count} accepted rows; "
                f"{workbook_report.accepted_record_pct:.2f}% acceptance"
            )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"FAIL data contract: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
