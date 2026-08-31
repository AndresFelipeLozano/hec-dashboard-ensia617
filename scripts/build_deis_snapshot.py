#!/usr/bin/env python3
"""Build the dashboard's minimal DEIS snapshot from validated ETL outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


OUTPUT_COLUMNS = [
    "establishment_code",
    "establishment_name",
    "commune_code",
    "commune_name",
    "establishment_type",
    "health_system_type",
    "care_level",
    "complexity_level",
    "emergency_type",
    "operating_status",
    "latitude",
    "longitude",
    "coordinates_available",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_snapshot(
    curated_path: Path,
    service_list_path: Path,
    upstream_manifest_path: Path,
    output_path: Path,
    manifest_path: Path,
) -> dict[str, object]:
    with service_list_path.open("r", encoding="utf-8-sig", newline="") as handle:
        selected_codes = {
            row["establecimiento_codigo"] for row in csv.DictReader(handle)
        }
    with curated_path.open("r", encoding="utf-8-sig", newline="") as handle:
        curated = {
            row["establecimiento_codigo"]: row for row in csv.DictReader(handle)
        }
    missing = sorted(selected_codes - set(curated))
    if missing:
        raise ValueError(
            "Service-list codes missing from CURATED: " + ", ".join(missing)
        )

    rows = []
    for code in sorted(selected_codes):
        source = curated[code]
        rows.append(
            {
                "establishment_code": code,
                "establishment_name": source["establecimiento"],
                "commune_code": source["comuna_codigo"],
                "commune_name": source["comuna"],
                "establishment_type": source["tipo_establecimiento"],
                "health_system_type": source["tipo_sistema_salud"],
                "care_level": source["nivel_atencion"],
                "complexity_level": source["nivel_complejidad"],
                "emergency_type": source["tipo_urgencia"],
                "operating_status": source["estado_funcionamiento"],
                "latitude": source["latitud"],
                "longitude": source["longitud"],
                "coordinates_available": source["tiene_coordenadas"],
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with upstream_manifest_path.open("r", encoding="utf-8") as handle:
        upstream_manifest = json.load(handle)
    manifest = {
        "snapshot_id": "deis_ssmc_2026-08-25_etl-0.1.0",
        "status": "packaged_public_reference",
        "created_at_utc": upstream_manifest["created_at_utc"],
        "scope": "vigentes_del_servicio_de_salud_metropolitano_central",
        "source_authority": "DEIS, Ministerio de Salud de Chile",
        "source_cut": "2026-08-25",
        "upstream_etl_version": upstream_manifest["curated_version"],
        "upstream_validation": {
            "pass": upstream_manifest["validation_pass"],
            "warn": upstream_manifest["validation_warn"],
            "fail": upstream_manifest["validation_fail"],
        },
        "source_files": [
            {
                "role": "curated_master",
                "filename": curated_path.name,
                "sha256": sha256(curated_path),
            },
            {
                "role": "validated_hec_service_selection",
                "filename": service_list_path.name,
                "sha256": sha256(service_list_path),
            },
            {
                "role": "upstream_curated_manifest",
                "filename": upstream_manifest_path.name,
                "sha256": sha256(upstream_manifest_path),
            },
        ],
        "rows": len(rows),
        "unique_establishment_codes": len({row["establishment_code"] for row in rows}),
        "rows_with_coordinates": sum(
            1
            for row in rows
            if row["latitude"] not in {"", None}
            and row["longitude"] not in {"", None}
        ),
        "output_file": output_path.name,
        "output_sha256": sha256(output_path),
        "privacy_boundary": "Contains establishment-level public reference data only; no patient or employee data.",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--curated", type=Path, required=True)
    parser.add_argument("--service-list", type=Path, required=True)
    parser.add_argument("--upstream-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_snapshot(
        args.curated,
        args.service_list,
        args.upstream_manifest,
        args.output,
        args.manifest,
    )
    print(
        "PASS DEIS snapshot: "
        f"{manifest['rows']} rows; "
        f"{manifest['rows_with_coordinates']} with coordinates; "
        f"sha256={manifest['output_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
