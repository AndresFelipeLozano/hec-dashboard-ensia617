from __future__ import annotations

from collections import Counter
from datetime import date
import json
from pathlib import Path
import sys
from time import perf_counter
import unittest
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from audit_day4_coverage import audit_coverage  # noqa: E402
from generate_simulated_data import _csv_text, generate_dataset  # noqa: E402
from hec_dashboard.app_state import (  # noqa: E402
    Keys,
    _load_bundled_cached,
    initialize_session,
    set_role_context,
)
from hec_dashboard.data_ingestion import load_workbook_tables, validate_workbook  # noqa: E402
from hec_dashboard.presentation import build_role_presentation  # noqa: E402


class Day4RemediationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        state = {}
        initialize_session(state)
        cls.dataset = state[Keys.ACTIVE_DATASET]
        cls.current = state[Keys.SELECTED_CURRENT_PERIOD]
        cls.previous = state[Keys.SELECTED_PREVIOUS_PERIOD]

    def test_generation_has_required_size_unique_ids_and_periods(self):
        tables, metadata = generate_dataset()
        self.assertEqual(sum(metadata["row_counts"].values()), 15200)
        self.assertEqual(metadata["row_counts"]["LISTA_ESPERA_AMB"], 6240)
        key_by_sheet = {
            "DERIVACIONES": "referral_id",
            "CIRUGIAS": "surgery_case_id",
            "ACTIVIDAD_PROF": "activity_id",
            "LISTA_ESPERA_AMB": "wait_episode_id",
        }
        for sheet, rows in tables.items():
            with self.subTest(sheet=sheet):
                ids = [row[key_by_sheet[sheet]] for row in rows]
                self.assertEqual(len(ids), len(set(ids)))
                date_field = (
                    "snapshot_date" if sheet == "LISTA_ESPERA_AMB" else "period_date"
                )
                quarters = Counter(
                    "Q1" if str(row[date_field]) < "2026-04-01" else "Q2"
                    for row in rows
                )
                self.assertGreater(quarters["Q1"], 0)
                self.assertGreater(quarters["Q2"], 0)

    def test_generation_is_deterministic_in_memory(self):
        first_tables, first_metadata = generate_dataset()
        second_tables, second_metadata = generate_dataset()
        self.assertEqual(first_metadata, second_metadata)
        for sheet in first_tables:
            self.assertEqual(
                _csv_text(first_tables[sheet]), _csv_text(second_tables[sheet])
            )

    def test_reserved_denominators_have_safety_margin(self):
        tables, _metadata = generate_dataset()
        for quarter, start, end in (
            ("Q1", "2026-01-01", "2026-03-31"),
            ("Q2", "2026-04-01", "2026-06-30"),
        ):
            referrals = [
                row
                for row in tables["DERIVACIONES"]
                if start <= row["period_date"] <= end
            ]
            referral_strata = {
                (row["service_id"], row["specialty_id"]) for row in referrals
            }
            for service_id, specialty_id in referral_strata:
                rows = [
                    row
                    for row in referrals
                    if row["service_id"] == service_id
                    and row["specialty_id"] == specialty_id
                ]
                for referral_type in ("new", "followup"):
                    denominator = sum(
                        row["referral_type"] == referral_type
                        and row["scheduled_flag"] == "SI"
                        for row in rows
                    )
                    self.assertGreaterEqual(
                        denominator,
                        40,
                        (quarter, service_id, specialty_id, referral_type),
                    )
            surgeries = [
                row
                for row in tables["CIRUGIAS"]
                if start <= row["period_date"] <= end
            ]
            surgery_strata = {
                (row["service_id"], row["specialty_id"]) for row in surgeries
            }
            for service_id, specialty_id in surgery_strata:
                completed = sum(
                    row["service_id"] == service_id
                    and row["specialty_id"] == specialty_id
                    and row["status"] == "completed"
                    and row["elective_major_flag"] == "SI"
                    for row in surgeries
                )
                self.assertGreaterEqual(
                    completed, 40, (quarter, service_id, specialty_id)
                )

    def test_independent_coverage_audit_has_no_failure(self):
        report = audit_coverage(REPO_ROOT)
        self.assertEqual(report["dataset_id"], "hec-sim-day5-v1")
        self.assertEqual(report["accepted_rows"], 15200)
        self.assertGreaterEqual(report["context_count"], 74)
        self.assertEqual(report["failure_count"], 0, report["failures"])

    def test_role_context_normalization_clears_incompatible_fields(self):
        state = {}
        set_role_context(
            state,
            {
                "role_id": "service_chief_clinical",
                "category": "Jefe de Servicio",
                "dashboard_type": "clinical",
                "service_id": "medicina_interna",
                "specialty_id": "medicina_interna",
                "simulated_profile_key": "SIM-STALE",
                "professional_lens": "surgical",
            },
        )
        self.assertNotIn("simulated_profile_key", state[Keys.ROLE_CONTEXT])
        self.assertNotIn("professional_lens", state[Keys.ROLE_CONTEXT])
        set_role_context(
            state,
            {
                "role_id": "professional_surgical",
                "category": "Profesional",
                "profile_type": "surgical",
                "simulated_profile_key": "SIM-PROF-S-TRAUMATOLOGIA-A",
                "professional_id": "SIM-PROF-S-TRAUMATOLOGIA-A",
                "professional_lens": "surgical",
                "service_id": "traumatologia",
                "specialty_id": "traumatologia",
            },
        )
        self.assertEqual(state[Keys.ROLE_CONTEXT]["service_id"], "traumatologia")
        self.assertEqual(state[Keys.ROLE_CONTEXT]["specialty_id"], "traumatologia")
        self.assertEqual(
            state[Keys.ROLE_CONTEXT]["specialty_display_name"], "Traumatología"
        )
        self.assertEqual(state[Keys.PENDING_NAVIGATION], "dashboard")

    def test_workbook_structure_and_contract_are_preserved(self):
        workbook = REPO_ROOT / "templates" / "plantilla_carga_hec_v1.xlsx"
        report = validate_workbook(workbook, REPO_ROOT)
        self.assertTrue(report.activatable)
        self.assertEqual(report.accepted_row_count, 15200)
        self.assertEqual(report.rejected_row_count, 0)
        tables = load_workbook_tables(workbook)
        self.assertEqual(
            list(tables),
            [
                "INSTRUCCIONES",
                "METADATOS",
                "DERIVACIONES",
                "CIRUGIAS",
                "ACTIVIDAD_PROF",
                "CATALOGOS",
                "LISTA_ESPERA_AMB",
            ],
        )
        professional_headers = tables["ACTIVIDAD_PROF"][0]
        self.assertEqual(len(professional_headers), 18)
        self.assertEqual(
            professional_headers.index("elective_major_applicable_flag") + 1,
            professional_headers.index("ambulatory_major_flag"),
        )
        with zipfile.ZipFile(workbook) as archive:
            for sheet_number in (3, 4, 5, 7):
                xml = archive.read(
                    f"xl/worksheets/sheet{sheet_number}.xml"
                ).decode("utf-8")
                self.assertIn("15000\"", xml)

    def test_deterministic_artifacts_match_external_network_remediation(self):
        metadata = json.loads(
            (REPO_ROOT / "data" / "simulated" / "metadata.json").read_text()
        )
        self.assertEqual(
            metadata["artifact_checksums_sha256"],
            {
                "derivaciones_simuladas.csv": "6e9b1c6678e3a128ee5764d0cefbe1c105ce7c3b6afe23594c014e116045240e",
                "cirugias_simuladas.csv": "c5151163537710dd900fed6f91e8950cad5e09597c12153b1c8da637ae4286d8",
                "actividad_profesional_simulada.csv": "c462b51e5bc6314d57ec933e468d6990be9e82e701554d9f48c6ed944e2988db",
                "lista_espera_ambulatoria_simulada.csv": "0a92d90ad2dd9f3b1a7ed42a4220ac289241f057bc8ec837f20775fa4ea56af7",
            },
        )

    def test_expanded_dataset_remains_responsive(self):
        _load_bundled_cached.cache_clear()
        started = perf_counter()
        state = {}
        initialize_session(state)
        bundled_seconds = perf_counter() - started
        started = perf_counter()
        cards = build_role_presentation(
            "service_chief_clinical",
            state[Keys.ACTIVE_DATASET],
            self.current,
            self.previous,
            service_id="alivio_dolor_cuidados_paliativos",
        )
        calculation_seconds = perf_counter() - started
        self.assertTrue(all(card.is_available for card in cards))
        self.assertLess(bundled_seconds, 5.0)
        self.assertLess(calculation_seconds, 1.0)


if __name__ == "__main__":
    unittest.main()
