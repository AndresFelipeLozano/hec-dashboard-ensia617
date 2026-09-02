from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from hec_dashboard.app_state import Keys, initialize_session  # noqa: E402
from hec_dashboard.app_config import (  # noqa: E402
    professional_lens_context,
    professional_profiles,
)
from hec_dashboard.data_ingestion import CandidateDataset, validate_tables  # noqa: E402
from hec_dashboard.indicator_engine import IndicatorEngine  # noqa: E402
from hec_dashboard.presentation import (  # noqa: E402
    build_mixed_presentations,
    build_role_presentation,
)
from validate_data_contract import load_simulated_tables  # noqa: E402


class Day4RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = load_simulated_tables(REPO_ROOT)
        state = {}
        initialize_session(state)
        cls.dataset = state[Keys.ACTIVE_DATASET]
        cls.current = state[Keys.SELECTED_CURRENT_PERIOD]
        cls.previous = state[Keys.SELECTED_PREVIOUS_PERIOD]
        cls.clinical_profile = professional_profiles("clinical")[0]
        cls.surgical_profile = professional_profiles("surgical")[0]
        cls.mixed_profile = professional_profiles("mixed")[0]

    def _profile_kwargs(self, profile, lens):
        scope = professional_lens_context(profile, lens)
        return {
            "service_id": scope["service_id"],
            "specialty_id": scope["specialty_id"],
            "simulated_profile_key": profile["professional_id"],
        }

    def _prof_column(self, tables, name):
        return tables["ACTIVIDAD_PROF"][0].index(name)

    def test_missing_elective_applicability_field_is_rejected(self):
        tables = copy.deepcopy(self.tables)
        column = self._prof_column(tables, "elective_major_applicable_flag")
        for row in tables["ACTIVIDAD_PROF"]:
            del row[column]
        report = validate_tables(tables, REPO_ROOT)
        self.assertFalse(report.activatable)
        self.assertIn("STRUCT_COLUMNS", {i.code for i in report.structural_errors})

    def test_invalid_elective_applicability_value_is_rejected(self):
        tables = copy.deepcopy(self.tables)
        column = self._prof_column(tables, "elective_major_applicable_flag")
        tables["ACTIVIDAD_PROF"][1][column] = "AMBIGUO"
        report = validate_tables(tables, REPO_ROOT)
        self.assertEqual(report.rejected_row_count, 1)
        self.assertIn("ROW_INVALID_VALUE", {i.code for i in report.issues})

    def test_clinical_activity_marked_applicable_is_rejected(self):
        tables = copy.deepcopy(self.tables)
        lens = self._prof_column(tables, "lens")
        applicable = self._prof_column(tables, "elective_major_applicable_flag")
        row = next(row for row in tables["ACTIVIDAD_PROF"][1:] if row[lens] == "clinical")
        row[applicable] = "SI"
        report = validate_tables(tables, REPO_ROOT)
        self.assertEqual(report.rejected_row_count, 1)
        self.assertIn("ROW_CLINICAL_FLAG_CONTRADICTION", {i.code for i in report.issues})

    def test_clinical_activity_cannot_enter_professional_ambulatory_denominator(self):
        dataset = copy.deepcopy(self.dataset)
        clinical = next(
            row
            for row in dataset.tables["ACTIVIDAD_PROF"]
            if row["lens"] == "clinical" and self.current[0] <= row["period_date"] <= self.current[1]
        )
        clinical["elective_major_applicable_flag"] = True
        clinical["ambulatory_major_flag"] = True
        before = build_role_presentation(
            "professional_surgical",
            self.dataset,
            self.current,
            self.previous,
            **self._profile_kwargs(self.surgical_profile, "surgical"),
        )
        cards = build_role_presentation(
            "professional_surgical",
            dataset,
            self.current,
            self.previous,
            **self._profile_kwargs(self.surgical_profile, "surgical"),
        )
        before_result = next(
            card
            for card in before
            if card.indicator_id == "professional_ambulatory_surgery_pct"
        )
        result = next(
            card for card in cards if card.indicator_id == "professional_ambulatory_surgery_pct"
        )
        self.assertEqual(result.denominator, before_result.denominator)
        self.assertEqual(result.numerator, before_result.numerator)

    def test_surgical_ambulatory_numerator_cannot_exceed_eligible_denominator(self):
        cards = build_role_presentation(
            "professional_surgical",
            self.dataset,
            self.current,
            self.previous,
            **self._profile_kwargs(self.surgical_profile, "surgical"),
        )
        result = next(
            card for card in cards if card.indicator_id == "professional_ambulatory_surgery_pct"
        )
        self.assertLessEqual(result.numerator, result.denominator)

    def test_median_calculation_isolated_and_deterministic(self):
        parts = IndicatorEngine._referral_wait_median(
            self.dataset,
            [{"wait_days": 9}, {"wait_days": 1}, {"wait_days": 5}],
            [],
        )
        self.assertEqual(parts.value, 5)
        self.assertEqual(parts.valid_n, 3)

    def test_documentation_completeness_differs_by_lens(self):
        clinical = build_role_presentation(
            "professional_clinical",
            self.dataset,
            self.current,
            self.previous,
            **self._profile_kwargs(self.clinical_profile, "clinical"),
        )
        surgical = build_role_presentation(
            "professional_surgical",
            self.dataset,
            self.current,
            self.previous,
            **self._profile_kwargs(self.surgical_profile, "surgical"),
        )
        clinical_value = next(
            card for card in clinical if card.indicator_id == "professional_documentation_completeness_pct"
        )
        surgical_value = next(
            card for card in surgical if card.indicator_id == "professional_documentation_completeness_pct"
        )
        self.assertTrue(clinical_value.is_available)
        self.assertTrue(surgical_value.is_available)
        self.assertEqual(clinical_value.filters["professional_lens"], "clinical")
        self.assertEqual(surgical_value.filters["professional_lens"], "surgical")

    def test_presentation_adapter_always_supplies_professional_lens(self):
        for role_id, expected, profile in (
            ("professional_clinical", "clinical", self.clinical_profile),
            ("professional_surgical", "surgical", self.surgical_profile),
        ):
            cards = build_role_presentation(
                role_id,
                self.dataset,
                self.current,
                self.previous,
                **self._profile_kwargs(profile, expected),
            )
            self.assertTrue(cards)
            self.assertTrue(
                all(card.filters.get("professional_lens") == expected for card in cards)
            )

    def test_mixed_presentation_never_produces_combined_score(self):
        groups = build_mixed_presentations(
            self.dataset,
            self.current,
            self.previous,
            self.mixed_profile["professional_id"],
            lens_contexts={
                lens: professional_lens_context(self.mixed_profile, lens)
                for lens in ("clinical", "surgical")
            },
        )
        self.assertEqual(set(groups), {"clinical", "surgical"})
        all_ids = [card.indicator_id for cards in groups.values() for card in cards]
        self.assertNotIn("combined_score", all_ids)


if __name__ == "__main__":
    unittest.main()
