#!/usr/bin/env python3
"""Generate deterministic, identifier-free-of-person simulated Day 2 data."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data" / "simulated"
SEED = 617
MONTHS = [f"2026-{month:02d}-01" for month in range(1, 7)]


def load_catalogs() -> tuple[dict[str, dict], dict[str, list[str]], list[str]]:
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
    with (
        REPO_ROOT / "data" / "reference" / "deis_establishments_ssmc_snapshot.csv"
    ).open("r", encoding="utf-8", newline="") as handle:
        origins = [
            row["establishment_code"]
            for row in csv.DictReader(handle)
            if row["coordinates_available"].casefold() == "true"
            and row["commune_name"] in {"Maipú", "Cerrillos", "Estación Central", "Santiago"}
        ]
    return units, specialties, origins


def write_csv(name: str, rows: list[dict[str, object]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def yes_no(value: bool) -> str:
    return "SI" if value else "NO"


def choose_service(
    rng: random.Random,
    units: dict[str, dict],
    dashboard_type: str,
) -> str:
    values = [
        unit_id
        for unit_id, item in units.items()
        if item["dashboard_type"] == dashboard_type
    ]
    return rng.choice(values)


def choose_specialty(
    rng: random.Random, specialties: dict[str, list[str]], service_id: str
) -> str:
    values = specialties[service_id]
    return rng.choice(values) if values and rng.random() < 0.85 else ""


def build_referrals(
    rng: random.Random,
    units: dict[str, dict],
    specialties: dict[str, list[str]],
    origins: list[str],
) -> list[dict[str, object]]:
    rows = []
    for index in range(1, 241):
        service_id = choose_service(rng, units, "clinical")
        referral_type = rng.choices(
            ["new", "followup", "teleconsult"], weights=[55, 30, 15]
        )[0]
        scheduled = rng.random() < 0.88
        no_show = scheduled and rng.random() < 0.11
        status = (
            "waiting"
            if rng.random() < 0.20
            else ("discharged" if rng.random() < 0.18 else "completed")
        )
        ges_applicable = rng.random() < 0.22
        ges_due = ges_applicable and rng.random() < 0.75
        rows.append(
            {
                "referral_id": f"SIM-REF-{index:05d}",
                "period_date": MONTHS[(index - 1) % len(MONTHS)],
                "service_id": service_id,
                "specialty_id": choose_specialty(rng, specialties, service_id),
                "origin_establishment_code": rng.choice(origins[:12]),
                "referral_type": referral_type,
                "status": status,
                "wait_days": max(0, round(rng.gauss(52, 24))),
                "scheduled_flag": yes_no(scheduled),
                "no_show_flag": yes_no(no_show),
                "pertinence_assessment": rng.choices(
                    ["pertinent", "not_pertinent", "not_assessed"],
                    weights=[77, 13, 10],
                )[0],
                "contrareference_flag": yes_no(
                    status == "discharged" and rng.random() < 0.73
                ),
                "ges_applicable_flag": yes_no(ges_applicable),
                "ges_due_flag": yes_no(ges_due),
                "ges_met_flag": yes_no(ges_due and rng.random() < 0.91),
                "teleconsult_timely_closed_flag": yes_no(
                    referral_type == "teleconsult" and rng.random() < 0.84
                ),
                "documentation_complete_flag": yes_no(rng.random() < 0.96),
            }
        )
    return rows


def build_surgeries(
    rng: random.Random,
    units: dict[str, dict],
    specialties: dict[str, list[str]],
    origins: list[str],
) -> list[dict[str, object]]:
    procedures = ["PROC-CMA", "PROC-CIR", "PROC-TRA", "PROC-URO", "PROC-ORL"]
    rows = []
    for index in range(1, 145):
        service_id = choose_service(rng, units, "surgical")
        status = rng.choices(
            ["waitlisted", "completed", "resolved", "suspended"],
            weights=[28, 48, 17, 7],
        )[0]
        elective = rng.random() < 0.86
        available = rng.choice([4.0, 6.0, 8.0])
        used = round(available * rng.uniform(0.55, 0.98), 2)
        rows.append(
            {
                "surgery_case_id": f"SIM-SUR-{index:05d}",
                "period_date": MONTHS[(index - 1) % len(MONTHS)],
                "service_id": service_id,
                "specialty_id": choose_specialty(rng, specialties, service_id),
                "origin_establishment_code": rng.choice(origins[:12]),
                "procedure_code": rng.choice(procedures),
                "status": status,
                "wait_days": max(0, round(rng.gauss(88, 38))),
                "elective_major_flag": yes_no(elective),
                "ambulatory_flag": yes_no(elective and rng.random() < 0.43),
                "scheduled_flag": yes_no(status != "waitlisted"),
                "or_hours_used": used,
                "or_hours_available": available,
                "documentation_complete_flag": yes_no(rng.random() < 0.97),
            }
        )
    return rows


def build_professional_activity(
    rng: random.Random,
    units: dict[str, dict],
    specialties: dict[str, list[str]],
    origins: list[str],
) -> list[dict[str, object]]:
    profile_cycle = [
        ("SIM-CLINICO-A", "clinical", "clinical"),
        ("SIM-QUIRURGICO-A", "surgical", "surgical"),
        ("SIM-MIXTO-A", "mixed", "clinical"),
        ("SIM-MIXTO-A", "mixed", "surgical"),
    ]
    rows = []
    for index in range(1, 217):
        profile_key, profile_type, lens = profile_cycle[(index - 1) % 4]
        service_id = choose_service(rng, units, lens)
        scheduled = rng.random() < 0.91
        completed = scheduled and rng.random() < 0.88
        clinical = lens == "clinical"
        rows.append(
            {
                "activity_id": f"SIM-ACT-{index:05d}",
                "period_date": MONTHS[(index - 1) % len(MONTHS)],
                "simulated_profile_key": profile_key,
                "profile_type": profile_type,
                "lens": lens,
                "service_id": service_id,
                "specialty_id": choose_specialty(rng, specialties, service_id),
                "origin_establishment_code": rng.choice(origins[:12]),
                "activity_code": (
                    rng.choice(["CONS-NUEVA", "CONS-CONTROL", "TELECONS"])
                    if clinical
                    else rng.choice(["PROC-CMA", "PROC-CIR", "PROC-TRA"])
                ),
                "scheduled_flag": yes_no(scheduled),
                "completed_flag": yes_no(completed),
                "no_show_flag": yes_no(clinical and scheduled and not completed and rng.random() < 0.65),
                "suspended_flag": yes_no((not clinical) and scheduled and not completed and rng.random() < 0.55),
                "new_consultation_flag": yes_no(clinical and rng.random() < 0.42),
                "discharge_flag": yes_no(clinical and completed and rng.random() < 0.16),
                "ambulatory_major_flag": yes_no((not clinical) and completed and rng.random() < 0.46),
                "documentation_complete_flag": yes_no(rng.random() < 0.96),
            }
        )
    return rows


def main() -> int:
    rng = random.Random(SEED)
    units, specialties, origins = load_catalogs()
    if len(origins) < 12:
        raise RuntimeError("At least 12 mapped DEIS origins are required")
    referrals = build_referrals(rng, units, specialties, origins)
    surgeries = build_surgeries(rng, units, specialties, origins)
    professional = build_professional_activity(rng, units, specialties, origins)
    write_csv("derivaciones_simuladas.csv", referrals)
    write_csv("cirugias_simuladas.csv", surgeries)
    write_csv("actividad_profesional_simulada.csv", professional)
    metadata = {
        "contract_version": "1.0.0",
        "dataset_id": "hec-sim-day2-v1",
        "dataset_name": "Demostración HEC — Día 2",
        "source_mode": "simulado",
        "period_start": "2026-01-01",
        "period_end": "2026-06-30",
        "generated_at_utc": "2026-08-31T12:00:00Z",
        "simulation_notice_es": "Datos operacionales y perfiles profesionales completamente simulados.",
        "deis_snapshot_id": "deis_ssmc_2026-08-25_etl-0.1.0",
        "seed": SEED,
        "row_counts": {
            "DERIVACIONES": len(referrals),
            "CIRUGIAS": len(surgeries),
            "ACTIVIDAD_PROF": len(professional),
        },
    }
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS simulated data: "
        f"{len(referrals)} referrals; {len(surgeries)} surgeries; "
        f"{len(professional)} professional activities; seed={SEED}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
