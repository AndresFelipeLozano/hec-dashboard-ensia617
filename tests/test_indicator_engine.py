from __future__ import annotations

from datetime import date
import json
import math
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from calculate_indicators import build_snapshot, load_packaged_candidate  # noqa: E402
from hec_dashboard.indicator_engine import (  # noqa: E402
    IndicatorContext,
    IndicatorEngine,
    _percentile,
)


class IndicatorEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = load_packaged_candidate(REPO_ROOT)
        cls.engine = IndicatorEngine.from_repo(REPO_ROOT)
        cls.context = IndicatorContext(
            period_start=date(2026, 4, 1),
            period_end=date(2026, 6, 30),
            previous_period_start=date(2026, 1, 1),
            previous_period_end=date(2026, 3, 31),
        )

    def test_bindings_cover_the_approved_catalog_exactly(self):
        self.assertEqual(set(self.engine.indicators), set(self.engine.bindings))
        self.assertEqual(len(self.engine.indicators), 31)

    def test_calculate_all_returns_each_indicator_once(self):
        results = self.engine.calculate_all(self.dataset, self.context)
        ids = [result.indicator_id for result in results]
        self.assertEqual(len(ids), 31)
        self.assertEqual(len(set(ids)), 31)
        self.assertEqual(set(ids), set(self.engine.indicators))

    def test_snapshot_is_json_safe_and_contains_no_nonfinite_values(self):
        snapshot = build_snapshot(REPO_ROOT)
        encoded = json.dumps(snapshot, allow_nan=False)
        self.assertTrue(encoded)
        for result in snapshot["results"]:
            for field in ("value", "prior_value", "numerator", "denominator"):
                value = result[field]
                if isinstance(value, float):
                    self.assertTrue(math.isfinite(value))

    def test_growth_uses_previous_comparable_period(self):
        result = self.engine.calculate(
            "referral_growth_pct", self.dataset, self.context
        )
        self.assertEqual(result.status, "available")
        self.assertEqual(result.numerator, 0)
        self.assertEqual(result.denominator, 120)
        self.assertEqual(result.value, 0.0)

    def test_zero_denominator_is_unavailable_not_zero(self):
        context = IndicatorContext(
            period_start=date(2026, 4, 1),
            period_end=date(2026, 6, 30),
            activity_code="nonexistent",
        )
        result = self.engine.calculate("new_no_show_pct", self.dataset, context)
        self.assertEqual(result.status, "zero_denominator")
        self.assertIsNone(result.value)
        self.assertEqual(result.denominator, 0)

    def test_insufficient_n_is_unavailable_not_zero(self):
        context = IndicatorContext(
            period_start=date(2026, 4, 1),
            period_end=date(2026, 6, 30),
            service_id="psiquiatria_infantil",
        )
        result = self.engine.calculate("wait_p75_days", self.dataset, context)
        self.assertEqual(result.status, "insufficient_n")
        self.assertIsNone(result.value)
        self.assertLess(result.valid_n, result.minimum_valid_n)

    def test_linear_percentile_is_deterministic(self):
        self.assertEqual(_percentile([0, 10, 20, 30], 0.75), 22.5)
        self.assertEqual(_percentile([5], 0.75), 5)

    def test_deferred_and_pending_indicators_never_emit_values(self):
        expected = {
            "surgical_waitlist_resolution_pct": "pending_definition",
            "operating_room_utilization_pct": "deferred",
            "emergency_bed_lt12h_pct": "deferred",
        }
        for indicator_id, status in expected.items():
            with self.subTest(indicator_id=indicator_id):
                result = self.engine.calculate(
                    indicator_id, self.dataset, self.context
                )
                self.assertEqual(result.status, status)
                self.assertIsNone(result.value)

    def test_pending_ministerial_reference_is_not_scored(self):
        result = self.engine.calculate("ges_compliance_pct", self.dataset, self.context)
        self.assertEqual(result.status, "available")
        self.assertEqual(result.reference["status"], "pending_applicability")

    def test_project_quality_reference_is_evaluated(self):
        result = self.engine.calculate("accepted_record_pct", self.dataset, self.context)
        self.assertEqual(result.value, 100.0)
        self.assertEqual(result.reference["status"], "met")

    def test_professional_ambulatory_denominator_uses_explicit_applicability(self):
        result = self.engine.calculate(
            "professional_ambulatory_surgery_pct", self.dataset, self.context
        )
        rows = [
            row
            for row in self.dataset.tables["ACTIVIDAD_PROF"]
            if row["lens"] == "surgical"
            and date(2026, 4, 1) <= row["period_date"] <= date(2026, 6, 30)
            and row["elective_major_applicable_flag"]
        ]
        self.assertEqual(result.denominator, len(rows))
        self.assertEqual(
            result.numerator, sum(row["ambulatory_major_flag"] for row in rows)
        )

    def test_indicator_profile_controls_applicability(self):
        context = IndicatorContext(
            period_start=date(2026, 4, 1),
            period_end=date(2026, 6, 30),
            indicator_profile="professional_surgical",
        )
        result = self.engine.calculate("new_no_show_pct", self.dataset, context)
        self.assertEqual(result.status, "not_applicable")
        self.assertIsNone(result.value)


if __name__ == "__main__":
    unittest.main()
