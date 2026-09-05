from __future__ import annotations

import copy
from datetime import date
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from audit_territorial_coverage import audit, supported_contexts  # noqa: E402
from generate_simulated_data import (  # noqa: E402
    generate_dataset,
    update_workbook,
    write_outputs,
)
from hec_dashboard.app_config import specialty_choices  # noqa: E402
from hec_dashboard.data_ingestion import CandidateDataset, validate_tables  # noqa: E402
from hec_dashboard.visual_analytics import (  # noqa: E402
    surgical_procedure_options,
    territorial_scope_summary,
)
from validate_data_contract import load_simulated_tables  # noqa: E402


Q1 = (date(2026, 1, 1), date(2026, 3, 31))
Q2 = (date(2026, 4, 1), date(2026, 6, 30))


class TerritorialCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        report = validate_tables(
            copy.deepcopy(load_simulated_tables(REPO_ROOT)), REPO_ROOT
        )
        cls.dataset = CandidateDataset(
            report.metadata, report.accepted_rows, report.summary()
        )

    def test_exhaustive_default_context_audit_passes(self):
        result = audit(REPO_ROOT)
        self.assertEqual(result["status"], "PASS", result["failures"][:5])
        self.assertEqual(result["default_contexts"], 74)
        self.assertEqual(result["period_contexts"], 148)
        self.assertEqual(result["procedure_period_contexts"], 110)
        self.assertGreaterEqual(result["minimum_publishable_markers"], 1)
        self.assertEqual(result["minimum_geographic_cell_n"], 10)
        self.assertTrue(result["deterministic_generation"])

    def test_every_supported_context_has_q1_and_q2_markers(self):
        for item in supported_contexts(REPO_ROOT):
            for current, previous in ((Q1, Q2), (Q2, Q1)):
                summary = territorial_scope_summary(
                    self.dataset, current, previous, item["context"]
                )
                self.assertTrue(
                    summary["rows"], (item["name"], current, summary)
                )
                self.assertTrue(
                    all(row["Episodios"] >= 10 for row in summary["rows"])
                )

    def test_role_appropriate_sources_and_mixed_lenses_are_independent(self):
        director = territorial_scope_summary(
            self.dataset, Q2, Q1, {"role_id": "director"}
        )
        palliative = territorial_scope_summary(
            self.dataset,
            Q2,
            Q1,
            {
                "role_id": "service_chief_clinical",
                "service_id": "alivio_dolor_cuidados_paliativos",
                "specialty_id": None,
            },
        )
        mixed_clinical = territorial_scope_summary(
            self.dataset,
            Q2,
            Q1,
            {
                "role_id": "professional_clinical",
                "service_id": "cirugia_infantil",
                "specialty_id": "cirugia_pediatrica",
                "simulated_profile_key": "SIM-PROF-M-PEDIATRICO-A",
                "professional_lens": "clinical",
            },
        )
        mixed_surgical = territorial_scope_summary(
            self.dataset,
            Q2,
            Q1,
            {
                "role_id": "professional_surgical",
                "service_id": "cirugia_infantil",
                "specialty_id": "cirugia_pediatrica",
                "simulated_profile_key": "SIM-PROF-M-PEDIATRICO-A",
                "professional_lens": "surgical",
            },
        )
        self.assertEqual(director["source"], "LISTA_ESPERA_AMB")
        self.assertEqual(palliative["source"], "DERIVACIONES")
        self.assertEqual(mixed_clinical["source"], "LISTA_ESPERA_AMB")
        self.assertEqual(mixed_surgical["source"], "CIRUGIAS")
        self.assertNotEqual(mixed_clinical["rows"], mixed_surgical["rows"])

    def test_palliative_has_no_specialty_and_five_markers_each_period(self):
        self.assertEqual(
            specialty_choices("alivio_dolor_cuidados_paliativos", REPO_ROOT), []
        )
        context = {
            "role_id": "service_chief_clinical",
            "service_id": "alivio_dolor_cuidados_paliativos",
            "specialty_id": None,
        }
        for current, previous in ((Q1, Q2), (Q2, Q1)):
            summary = territorial_scope_summary(
                self.dataset, current, previous, context
            )
            self.assertEqual(summary["aggregation_level"], "service")
            self.assertEqual(summary["publishable_cells"], 5)
            self.assertTrue(
                all("Alivio del Dolor" in row["Alcance activo"] for row in summary["rows"])
            )

    def test_each_surgical_procedure_has_publishable_coverage(self):
        context = {
            "role_id": "service_chief_surgical",
            "service_id": "urologia",
            "specialty_id": "urologia",
        }
        for current, previous in ((Q1, Q2), (Q2, Q1)):
            options = surgical_procedure_options(self.dataset, current, context)
            self.assertEqual(len(options), 5)
            for option in options:
                summary = territorial_scope_summary(
                    self.dataset,
                    current,
                    previous,
                    {**context, "procedure_code": option["procedure_code"]},
                )
                self.assertGreaterEqual(summary["publishable_cells"], 1)

    def test_professional_rows_and_exports_have_no_individual_attribution(self):
        context = {
            "role_id": "professional_surgical",
            "service_id": "urologia",
            "specialty_id": "urologia",
            "simulated_profile_key": "SIM-PROF-S-UROLOGIA-A",
            "professional_lens": "surgical",
        }
        rows = territorial_scope_summary(self.dataset, Q2, Q1, context)["rows"]
        forbidden = {
            "patient_id",
            "rut",
            "professional_profile_id",
            "simulated_profile_key",
            "surgery_case_id",
        }
        self.assertTrue(rows)
        self.assertTrue(all(not (set(row) & forbidden) for row in rows))
        self.assertTrue(
            all("SIM-PROF" not in str(value) for row in rows for value in row.values())
        )

    def test_two_full_generations_and_workbooks_are_byte_identical(self):
        with TemporaryDirectory() as first_dir, TemporaryDirectory() as second_dir:
            first_tables, first_metadata = generate_dataset()
            second_tables, second_metadata = generate_dataset()
            first_artifacts = write_outputs(
                Path(first_dir), first_tables, first_metadata
            )
            second_artifacts = write_outputs(
                Path(second_dir), second_tables, second_metadata
            )
            self.assertEqual(first_artifacts, second_artifacts)
            first_workbook = Path(first_dir) / "workbook.xlsx"
            second_workbook = Path(second_dir) / "workbook.xlsx"
            source = REPO_ROOT / "templates" / "plantilla_carga_hec_1_3.xlsx"
            update_workbook(source, first_workbook, first_tables, first_metadata)
            update_workbook(source, second_workbook, second_tables, second_metadata)
            self.assertEqual(first_workbook.read_bytes(), second_workbook.read_bytes())


if __name__ == "__main__":
    unittest.main()
