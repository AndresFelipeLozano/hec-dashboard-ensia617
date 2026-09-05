from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hec_dashboard.inpatient_reference import (  # noqa: E402
    ANNUAL_FIELDS,
    InpatientAccessError,
    InpatientIndicatorEngine,
    load_inpatient_reference,
    role_can_access_inpatient_reference,
)


class InpatientReferenceTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_inpatient_reference("director", repo_root=REPO_ROOT)
        self.engine = InpatientIndicatorEngine(self.dataset)

    def test_reference_is_one_hec_record_with_minimum_fields(self):
        self.assertEqual(tuple(self.dataset.annual), ANNUAL_FIELDS)
        self.assertEqual(self.dataset.annual["establishment_code"], "111101")
        self.assertEqual(self.dataset.annual["commune"], "Maipú")
        self.assertEqual(self.dataset.annual["performance_year"], 2025)
        excluded = {"address", "telephone", "latitude", "longitude"}
        self.assertFalse(excluded & set(self.dataset.annual))
        self.assertEqual(self.dataset.manifest["maipu_records"], 1)
        self.assertEqual(self.dataset.manifest["cerrillos_records"], 0)

    def test_curated_artifact_hashes_match_manifest(self):
        for path_key, hash_key in (
            ("annual_reference_file", "annual_reference_sha256"),
            ("monthly_reference_file", "monthly_reference_sha256"),
        ):
            path = REPO_ROOT / self.dataset.manifest[path_key]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                self.dataset.manifest[hash_key],
            )

    def test_annual_formulas_recompute_from_primitives(self):
        expected = {
            "inpatient_occupancy_pct": 91.72,
            "inpatient_average_beds": 411.48,
            "inpatient_average_length_of_stay_days": 8.13,
            "inpatient_discharges_total": 16446,
            "inpatient_crude_lethality_pct": 3.45,
        }
        for indicator_id, value in expected.items():
            with self.subTest(indicator_id=indicator_id):
                result = self.engine.calculate(indicator_id)
                self.assertEqual(result.status, "available")
                self.assertEqual(result.value, value)
                self.assertIsNone(result.prior_value)
                self.assertIsNone(result.previous_period_start)
                self.assertEqual(result.period_start.isoformat(), "2025-01-01")
                self.assertEqual(result.period_end.isoformat(), "2025-12-31")
                self.assertEqual(result.source_class, "curated_historical_reference")

    def test_monthly_primitives_reconcile_exactly_to_annual(self):
        self.assertEqual(len(self.dataset.monthly), 12)
        for field in (
            "available_bed_days",
            "occupied_bed_days",
            "total_stay_days",
            "discharges",
            "death_discharges",
        ):
            self.assertEqual(
                sum(int(row[field]) for row in self.dataset.monthly),
                self.dataset.annual[field],
            )
        january = self.engine.monthly_series("inpatient_occupancy_pct")[0]
        self.assertEqual(january.value, 92.04)
        self.assertEqual(january.period_end.isoformat(), "2025-01-31")

    def test_missing_and_zero_denominators_never_become_zero(self):
        missing_row = dict(self.dataset.annual)
        missing_row["occupied_bed_days"] = None
        missing = self.engine.calculate("inpatient_occupancy_pct", missing_row)
        self.assertEqual(missing.status, "unavailable")
        self.assertIsNone(missing.value)

        zero_row = dict(self.dataset.annual)
        zero_row["available_bed_days"] = 0
        zero = self.engine.calculate("inpatient_occupancy_pct", zero_row)
        self.assertEqual(zero.status, "zero_denominator")
        self.assertIsNone(zero.value)

    def test_role_access_is_configured_and_fails_closed(self):
        self.assertTrue(role_can_access_inpatient_reference("director", repo_root=REPO_ROOT))
        self.assertTrue(
            role_can_access_inpatient_reference("medical_director", repo_root=REPO_ROOT)
        )
        for role_id in (
            "service_chief_clinical",
            "service_chief_surgical",
            "professional_clinical",
            "professional_surgical",
            "professional_mixed",
        ):
            with self.subTest(role_id=role_id):
                self.assertFalse(
                    role_can_access_inpatient_reference(role_id, repo_root=REPO_ROOT)
                )
                with self.assertRaises(InpatientAccessError):
                    load_inpatient_reference(role_id, repo_root=REPO_ROOT)

    def test_lethality_is_explicitly_crude_and_unadjusted(self):
        result = self.engine.calculate("inpatient_crude_lethality_pct")
        explanation = result.reason_es.casefold()
        self.assertIn("bruta", explanation)
        self.assertIn("no ajustada", explanation)
        self.assertIn("no apta para rankings", explanation)
        self.assertIsNone(result.reference["value"])


if __name__ == "__main__":
    unittest.main()
