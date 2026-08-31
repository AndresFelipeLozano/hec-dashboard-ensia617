from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from hec_dashboard.data_ingestion import (  # noqa: E402
    SessionDatasetStore,
    validate_tables,
    validate_workbook,
)
from validate_data_contract import (  # noqa: E402
    load_simulated_tables,
    validate_snapshot,
)


class DataIngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = load_simulated_tables(REPO_ROOT)

    def test_packaged_simulation_is_fully_valid(self):
        report = validate_tables(
            copy.deepcopy(self.tables),
            REPO_ROOT,
            validation_timestamp_utc="2026-08-31T12:00:00+00:00",
        )
        self.assertTrue(report.activatable)
        self.assertEqual(report.accepted_row_count, 600)
        self.assertEqual(report.rejected_row_count, 0)
        self.assertEqual(report.accepted_record_pct, 100.0)
        self.assertEqual(report.critical_field_completeness_pct, 100.0)

    def test_packaged_workbook_round_trip_is_fully_valid(self):
        report = validate_workbook(
            REPO_ROOT / "templates" / "plantilla_carga_hec_v1.xlsx",
            REPO_ROOT,
        )
        self.assertTrue(report.activatable)
        self.assertEqual(report.accepted_row_count, 600)
        self.assertEqual(report.rejected_row_count, 0)

    def test_unmatched_deis_code_is_quarantined_actionably(self):
        tables = copy.deepcopy(self.tables)
        header = tables["DERIVACIONES"][0]
        column = header.index("origin_establishment_code")
        tables["DERIVACIONES"][1][column] = "999999"
        report = validate_tables(tables, REPO_ROOT)
        self.assertTrue(report.activatable)
        self.assertEqual(report.rejected_row_count, 1)
        self.assertEqual(report.issues[0].code, "ROW_UNMATCHED_DEIS_CODE")
        self.assertEqual(report.issues[0].sheet, "DERIVACIONES")
        self.assertEqual(report.issues[0].row, 2)

    def test_duplicate_identifier_is_quarantined(self):
        tables = copy.deepcopy(self.tables)
        header = tables["CIRUGIAS"][0]
        column = header.index("surgery_case_id")
        tables["CIRUGIAS"][2][column] = tables["CIRUGIAS"][1][column]
        report = validate_tables(tables, REPO_ROOT)
        self.assertTrue(report.activatable)
        self.assertEqual(report.rejected_row_count, 1)
        self.assertIn("ROW_DUPLICATE_ID", {issue.code for issue in report.issues})

    def test_unknown_sheet_warns_without_blocking_activation(self):
        tables = copy.deepcopy(self.tables)
        tables["NOTAS_LOCALES"] = [["texto"], ["ignorado"]]
        report = validate_tables(tables, REPO_ROOT)
        self.assertTrue(report.activatable)
        self.assertIn("STRUCT_UNKNOWN_SHEET", {issue.code for issue in report.issues})

    def test_failed_candidate_preserves_active_dataset(self):
        store = SessionDatasetStore()
        valid_report = store.submit_tables(copy.deepcopy(self.tables), REPO_ROOT)
        self.assertTrue(valid_report.activatable)
        active = store.activate_candidate()
        active_digest = hashlib.sha256(
            json.dumps(
                active.validation_summary, sort_keys=True
            ).encode("utf-8")
        ).hexdigest()

        invalid_tables = copy.deepcopy(self.tables)
        del invalid_tables["CIRUGIAS"]
        invalid_report = store.submit_tables(invalid_tables, REPO_ROOT)
        self.assertFalse(invalid_report.activatable)
        self.assertIsNone(store.candidate_dataset)
        self.assertIsNotNone(store.active_dataset)
        preserved_digest = hashlib.sha256(
            json.dumps(
                store.active_dataset.validation_summary, sort_keys=True
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(preserved_digest, active_digest)

    def test_activation_is_explicit(self):
        store = SessionDatasetStore()
        report = store.submit_tables(copy.deepcopy(self.tables), REPO_ROOT)
        self.assertTrue(report.activatable)
        self.assertIsNone(store.active_dataset)
        self.assertIsNotNone(store.candidate_dataset)
        store.activate_candidate()
        self.assertIsNotNone(store.active_dataset)

    def test_deis_snapshot_manifest_and_coordinates_are_valid(self):
        counts = validate_snapshot(REPO_ROOT)
        self.assertEqual(counts, {"rows": 55, "codes": 55})


if __name__ == "__main__":
    unittest.main()
