from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hec_dashboard.app_state import Keys, initialize_session  # noqa: E402
from hec_dashboard.app_config import (  # noqa: E402
    professional_lens_context,
    professional_profiles,
)
from hec_dashboard.indicator_engine import IndicatorResult  # noqa: E402
from hec_dashboard.presentation import (  # noqa: E402
    STATUS_LABELS,
    build_mixed_presentations,
    build_role_presentation,
    present_result,
)


class PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        state = {}
        initialize_session(state)
        cls.dataset = state[Keys.ACTIVE_DATASET]
        cls.current = state[Keys.SELECTED_CURRENT_PERIOD]
        cls.previous = state[Keys.SELECTED_PREVIOUS_PERIOD]
        cls.clinical_profile = professional_profiles("clinical")[0]
        cls.mixed_profile = professional_profiles("mixed")[0]

    def test_exact_primary_indicators_and_maximum_six(self):
        cards = build_role_presentation(
            "director", self.dataset, self.current, self.previous
        )
        self.assertEqual(
            [card.indicator_id for card in cards],
            [
                "referrals_total",
                "wait_p75_days",
                "ges_compliance_pct",
                "new_no_show_pct",
                "elective_surgery_suspension_pct",
                "accepted_record_pct",
            ],
        )
        self.assertLessEqual(len(cards), 6)

    def test_available_formatting_preserves_current_and_previous(self):
        cards = build_role_presentation(
            "director", self.dataset, self.current, self.previous
        )
        referrals = cards[0]
        self.assertEqual(referrals.value_text, "1.696")
        self.assertEqual(referrals.previous_text, "1.704")
        self.assertEqual(referrals.delta_text, "-8,0")

    def _result(self, status: str, value=None) -> IndicatorResult:
        return IndicatorResult(
            indicator_id="x",
            display_name_es="Indicador",
            status=status,
            value=value,
            prior_value=None,
            unit="percentage",
            numerator=None,
            denominator=0 if status == "zero_denominator" else None,
            valid_n=0,
            minimum_valid_n=1,
            reason_es="Motivo",
            reference={
                "status": "pending_applicability",
                "explanation_es": "Aplicabilidad pendiente",
            },
            period_start=date(2026, 4, 1),
            period_end=date(2026, 6, 30),
            previous_period_start=date(2026, 1, 1),
            previous_period_end=date(2026, 3, 31),
            filters={},
            calculation_basis_es=None,
        )

    def test_every_unavailable_status_never_substitutes_zero(self):
        for status in (
            "insufficient_n",
            "zero_denominator",
            "pending_definition",
            "deferred",
            "not_applicable",
        ):
            with self.subTest(status=status):
                card = present_result(self._result(status))
                self.assertFalse(card.is_available)
                self.assertEqual(card.value_text, STATUS_LABELS[status])
                self.assertNotEqual(card.value_text, "0")

    def test_target_reference_text_is_preserved(self):
        card = present_result(self._result("pending_definition"))
        self.assertEqual(card.target_text, "Aplicabilidad pendiente")

    def test_service_and_specialty_filters_propagate(self):
        cards = build_role_presentation(
            "service_chief_clinical",
            self.dataset,
            self.current,
            self.previous,
            service_id="especialidades_medicas_adulto",
            specialty_id="cardiologia_adulto",
        )
        self.assertTrue(
            all(card.filters["service_id"] == "especialidades_medicas_adulto" for card in cards)
        )
        self.assertTrue(
            all(card.filters["specialty_id"] == "cardiologia_adulto" for card in cards)
        )

    def test_professional_profile_and_mandatory_lens_propagate(self):
        profile = self.clinical_profile
        scope = professional_lens_context(profile, "clinical")
        cards = build_role_presentation(
            "professional_clinical",
            self.dataset,
            self.current,
            self.previous,
            service_id=scope["service_id"],
            specialty_id=scope["specialty_id"],
            simulated_profile_key=profile["professional_id"],
        )
        self.assertTrue(
            all(
                card.filters.get("simulated_profile_key")
                == profile["professional_id"]
                for card in cards
            )
        )
        self.assertTrue(
            all(card.filters.get("professional_lens") == "clinical" for card in cards)
        )

    def test_mixed_presentation_is_two_independent_lenses(self):
        profile = self.mixed_profile
        groups = build_mixed_presentations(
            self.dataset,
            self.current,
            self.previous,
            profile["professional_id"],
            lens_contexts={
                lens: professional_lens_context(profile, lens)
                for lens in ("clinical", "surgical")
            },
        )
        self.assertEqual(set(groups), {"clinical", "surgical"})
        self.assertNotIn("combined", groups)
        self.assertTrue(
            all(card.filters.get("professional_lens") == "clinical" for card in groups["clinical"])
        )
        self.assertTrue(
            all(card.filters.get("professional_lens") == "surgical" for card in groups["surgical"])
        )


if __name__ == "__main__":
    unittest.main()
