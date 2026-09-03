from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from streamlit.testing.v1 import AppTest  # noqa: E402

from audit_day4_coverage import audit_coverage  # noqa: E402
from hec_dashboard.app_config import (  # noqa: E402
    load_contract,
    professional_lens_context,
    professional_profiles,
    professional_specialty_choices,
)
from hec_dashboard.app_state import (  # noqa: E402
    Keys,
    initialize_session,
    set_role_context,
)
from hec_dashboard.presentation import (  # noqa: E402
    build_mixed_presentations,
    build_role_presentation,
)


class ProfessionalContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        state = {}
        initialize_session(state)
        cls.state = state
        cls.dataset = state[Keys.ACTIVE_DATASET]
        cls.current = state[Keys.SELECTED_CURRENT_PERIOD]
        cls.previous = state[Keys.SELECTED_PREVIOUS_PERIOD]
        services = load_contract("services")
        cls.specialty_by_id = {
            item["specialty_id"]: item
            for item in services["analytical_specialties"]
            if item.get("mvp_enabled")
        }

    def app(self) -> AppTest:
        return AppTest.from_file(
            str(REPO_ROOT / "app.py"), default_timeout=20
        ).run()

    def select_professional_draft(
        self, profile_type: str, specialty_index: int = 0
    ) -> tuple[AppTest, dict, dict]:
        variants = {
            "clinical": "Clínico",
            "surgical": "Quirúrgico",
            "mixed": "Mixto",
        }
        at = self.app()
        at.selectbox(key="role_category").set_value("Profesional").run()
        at.selectbox(key="role_variant").set_value(variants[profile_type]).run()
        specialty = professional_specialty_choices(profile_type)[specialty_index]
        at.selectbox(key=f"role_prof_specialty_{profile_type}").set_value(
            specialty["specialty_id"]
        ).run()
        profile = professional_profiles(
            profile_type, specialty["specialty_id"]
        )[0]
        at.selectbox(
            key=f"role_prof_profile_{profile_type}_{specialty['specialty_id']}"
        ).set_value(profile["professional_id"]).run()
        return at, specialty, profile

    def test_clinical_approach_lists_only_clinical_specialties(self):
        choices = professional_specialty_choices("clinical")
        self.assertEqual(len(choices), 15)
        self.assertTrue(
            all(
                self.specialty_by_id[item["specialty_id"]]["dashboard_type"]
                == "clinical"
                for item in choices
            )
        )

    def test_surgical_approach_lists_only_surgical_specialties(self):
        choices = professional_specialty_choices("surgical")
        self.assertEqual(len(choices), 11)
        self.assertTrue(
            all(
                self.specialty_by_id[item["specialty_id"]]["dashboard_type"]
                == "surgical"
                for item in choices
            )
        )

    def test_mixed_profile_uses_one_pediatric_surgery_specialty(self):
        profiles = professional_profiles("mixed")
        self.assertEqual(len(profiles), 1)
        profile = profiles[0]
        clinical = professional_lens_context(profile, "clinical")
        surgical = professional_lens_context(profile, "surgical")
        self.assertEqual(profile["specialty_id"], "cirugia_pediatrica")
        self.assertEqual(profile["service_id"], "cirugia_infantil")
        self.assertEqual(clinical["specialty_id"], "cirugia_pediatrica")
        self.assertEqual(surgical["specialty_id"], "cirugia_pediatrica")
        self.assertEqual(clinical["service_id"], surgical["service_id"])
        self.assertEqual(
            clinical["specialty_display_name"], "Cirugía Pediátrica"
        )
        self.assertEqual(clinical["activity_class"], "outpatient_clinical")
        self.assertEqual(surgical["activity_class"], "surgical_procedural")

    def test_mixed_rows_preserve_identity_specialty_and_activity_class(self):
        profile = professional_profiles("mixed")[0]
        rows = [
            row
            for row in self.dataset.tables["ACTIVIDAD_PROF"]
            if row["simulated_profile_key"] == profile["professional_id"]
        ]
        self.assertEqual(len(rows), 240)
        self.assertEqual(
            {row["simulated_profile_key"] for row in rows},
            {profile["professional_id"]},
        )
        self.assertEqual({row["specialty_id"] for row in rows}, {"cirugia_pediatrica"})
        self.assertEqual({row["service_id"] for row in rows}, {"cirugia_infantil"})
        clinical_codes = {
            row["activity_code"] for row in rows if row["lens"] == "clinical"
        }
        surgical_codes = {
            row["activity_code"] for row in rows if row["lens"] == "surgical"
        }
        self.assertTrue(all(code.startswith(("CONS-", "TELECONS")) for code in clinical_codes))
        self.assertTrue(all(code.startswith("PROC-") for code in surgical_codes))

    def test_mixed_lens_record_ids_are_disjoint(self):
        profile = professional_profiles("mixed")[0]
        ids = {
            lens: {
                row["activity_id"]
                for row in self.dataset.tables["ACTIVIDAD_PROF"]
                if row["simulated_profile_key"] == profile["professional_id"]
                and row["lens"] == lens
            }
            for lens in ("clinical", "surgical")
        }
        self.assertEqual(len(ids["clinical"]), 120)
        self.assertEqual(len(ids["surgical"]), 120)
        self.assertTrue(ids["clinical"].isdisjoint(ids["surgical"]))

    def test_mixed_lens_has_exact_period_coverage(self):
        profile = professional_profiles("mixed")[0]
        for lens in ("clinical", "surgical"):
            for start, end in (self.previous, self.current):
                rows = [
                    row
                    for row in self.dataset.tables["ACTIVIDAD_PROF"]
                    if row["simulated_profile_key"] == profile["professional_id"]
                    and row["lens"] == lens
                    and start <= row["period_date"] <= end
                ]
                self.assertEqual(len(rows), 60, (lens, start, end))

    def test_mixed_calculations_exclude_the_other_lens(self):
        profile = professional_profiles("mixed")[0]
        scope = professional_lens_context(profile, "clinical")
        clinical_before = build_role_presentation(
            "professional_clinical",
            self.dataset,
            self.current,
            self.previous,
            service_id=scope["service_id"],
            specialty_id=scope["specialty_id"],
            simulated_profile_key=profile["professional_id"],
        )
        changed = copy.deepcopy(self.dataset)
        for row in changed.tables["ACTIVIDAD_PROF"]:
            if row["simulated_profile_key"] == profile["professional_id"] and row["lens"] == "surgical":
                row["completed_flag"] = not row["completed_flag"]
                row["documentation_complete_flag"] = not row["documentation_complete_flag"]
        clinical_after = build_role_presentation(
            "professional_clinical",
            changed,
            self.current,
            self.previous,
            service_id=scope["service_id"],
            specialty_id=scope["specialty_id"],
            simulated_profile_key=profile["professional_id"],
        )
        self.assertEqual(clinical_before, clinical_after)

        surgical_scope = professional_lens_context(profile, "surgical")
        surgical_before = build_role_presentation(
            "professional_surgical",
            self.dataset,
            self.current,
            self.previous,
            service_id=surgical_scope["service_id"],
            specialty_id=surgical_scope["specialty_id"],
            simulated_profile_key=profile["professional_id"],
        )
        changed = copy.deepcopy(self.dataset)
        for row in changed.tables["ACTIVIDAD_PROF"]:
            if row["simulated_profile_key"] == profile["professional_id"] and row["lens"] == "clinical":
                row["completed_flag"] = not row["completed_flag"]
                row["documentation_complete_flag"] = not row["documentation_complete_flag"]
        surgical_after = build_role_presentation(
            "professional_surgical",
            changed,
            self.current,
            self.previous,
            service_id=surgical_scope["service_id"],
            specialty_id=surgical_scope["specialty_id"],
            simulated_profile_key=profile["professional_id"],
        )
        self.assertEqual(surgical_before, surgical_after)

    def test_mixed_context_preserves_shared_scope_across_lenses(self):
        profile = professional_profiles("mixed")[0]
        state = copy.deepcopy(self.state)
        set_role_context(
            state,
            {
                "role_id": "professional_mixed",
                "category": "Profesional",
                "profile_type": "mixed",
                "professional_id": profile["professional_id"],
                "simulated_profile_key": profile["professional_id"],
                "service_id": profile["service_id"],
                "specialty_id": profile["specialty_id"],
            },
        )
        stored = state[Keys.ROLE_CONTEXT]
        self.assertEqual(stored["professional_id"], profile["professional_id"])
        self.assertEqual(stored["specialty_id"], "cirugia_pediatrica")
        self.assertEqual(stored["specialty_display_name"], "Cirugía Pediátrica")
        for lens in ("clinical", "surgical"):
            scope = stored["professional_lens_contexts"][lens]
            self.assertEqual(scope["service_id"], stored["service_id"])
            self.assertEqual(scope["specialty_id"], stored["specialty_id"])

    def test_specialty_lists_only_compatible_profiles(self):
        for profile_type in ("clinical", "surgical", "mixed"):
            for specialty in professional_specialty_choices(profile_type):
                profiles = professional_profiles(
                    profile_type, specialty["specialty_id"]
                )
                self.assertTrue(profiles)
                self.assertTrue(
                    all(
                        item["profile_type"] == profile_type
                        and item["specialty_id"] == specialty["specialty_id"]
                        for item in profiles
                    )
                )

    def test_labels_include_specialty_and_are_not_internal_ids(self):
        for profile_type in ("clinical", "surgical", "mixed"):
            for profile in professional_profiles(profile_type):
                self.assertIn(
                    profile["specialty_display_name"], profile["display_label_es"]
                )
                self.assertNotEqual(
                    profile["professional_id"], profile["display_label_es"]
                )
                self.assertTrue(profile["simulated"])

    def test_submitted_context_is_atomic_and_readable(self):
        profile = professional_profiles("clinical")[0]
        context = {
            "role_id": "professional_clinical",
            "category": "Profesional",
            "profile_type": "clinical",
            "professional_id": profile["professional_id"],
            "simulated_profile_key": profile["professional_id"],
            "professional_lens": "clinical",
            "service_id": profile["service_id"],
            "specialty_id": profile["specialty_id"],
        }
        state = copy.deepcopy(self.state)
        set_role_context(state, context)
        stored = state[Keys.ROLE_CONTEXT]
        for key in (
            "professional_id",
            "professional_display_label",
            "specialty_id",
            "specialty_display_name",
            "current_period",
            "comparison_period",
            "active_dataset_id",
        ):
            self.assertTrue(stored[key], key)
        self.assertEqual(stored["active_dataset_id"], "hec-sim-day5-v1")

    def test_professional_calculation_filters_profile_specialty_and_service(self):
        profile = professional_profiles("clinical")[0]
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
        self.assertTrue(all(card.is_available for card in cards))
        self.assertTrue(
            all(
                card.filters["simulated_profile_key"]
                == profile["professional_id"]
                and card.filters["specialty_id"] == scope["specialty_id"]
                and card.filters["service_id"] == scope["service_id"]
                for card in cards
            )
        )

    def test_professional_scope_invariant_rejects_cross_specialty_rows(self):
        profile = professional_profiles("clinical")[0]
        scope = professional_lens_context(profile, "clinical")
        dataset = copy.deepcopy(self.dataset)
        row = next(
            item
            for item in dataset.tables["ACTIVIDAD_PROF"]
            if item["simulated_profile_key"] == profile["professional_id"]
        )
        row["specialty_id"] = "cardiologia_adulto"
        with self.assertRaisesRegex(ValueError, "otra especialidad"):
            build_role_presentation(
                "professional_clinical",
                dataset,
                self.current,
                self.previous,
                service_id=scope["service_id"],
                specialty_id=scope["specialty_id"],
                simulated_profile_key=profile["professional_id"],
            )

    def test_every_professional_profile_has_period_margin(self):
        for profile_type in ("clinical", "surgical", "mixed"):
            for profile in professional_profiles(profile_type):
                for lens in profile["supported_lenses"]:
                    for start, end in (self.previous, self.current):
                        rows = [
                            row
                            for row in self.dataset.tables["ACTIVIDAD_PROF"]
                            if row["simulated_profile_key"]
                            == profile["professional_id"]
                            and row["lens"] == lens
                            and start <= row["period_date"] <= end
                        ]
                        self.assertGreaterEqual(
                            len(rows), 40, (profile["professional_id"], lens)
                        )

    def test_coverage_audit_includes_all_professional_contexts(self):
        report = audit_coverage(REPO_ROOT)
        self.assertEqual(report["failure_count"], 0)
        self.assertEqual(report["integrity_failures"], [])
        self.assertEqual(
            report["context_counts_by_role"]["professional_clinical"], 15
        )
        self.assertEqual(
            report["context_counts_by_role"]["professional_surgical"], 11
        )
        self.assertEqual(
            report["context_counts_by_role"]["professional_mixed"], 2
        )
        self.assertEqual(len(report["mixed_profile_results"]), 4)
        self.assertEqual(report["mixed_composite_result_count"], 0)
        self.assertTrue(
            all(
                item["row_count"] == 60
                and item["specialty_id"] == "cirugia_pediatrica"
                and not item["incompatible_activity_ids"]
                and set(item["indicator_status_counts"]) == {"available"}
                for item in report["mixed_profile_results"]
            )
        )
        self.assertEqual(
            {
                (item["period"], item["lens"])
                for item in report["mixed_profile_results"]
            },
            {
                ("Q1", "clinical"),
                ("Q2", "clinical"),
                ("Q1", "surgical"),
                ("Q2", "surgical"),
            },
        )

    def test_changing_approach_clears_incompatible_widgets_immediately(self):
        at, clinical_specialty, _profile = self.select_professional_draft(
            "clinical"
        )
        clinical_profile_key = (
            f"role_prof_profile_clinical_{clinical_specialty['specialty_id']}"
        )
        self.assertIn(clinical_profile_key, at.session_state.filtered_state)
        at.selectbox(key="role_variant").set_value("Quirúrgico").run()
        state = at.session_state.filtered_state
        self.assertNotIn("role_prof_specialty_clinical", state)
        self.assertNotIn(clinical_profile_key, state)
        self.assertIsNone(at.selectbox(key="role_prof_specialty_surgical").value)
        surgical_specialty = professional_specialty_choices("surgical")[0]
        at.selectbox(key="role_prof_specialty_surgical").set_value(
            surgical_specialty["specialty_id"]
        ).run()
        surgical_profile = professional_profiles(
            "surgical", surgical_specialty["specialty_id"]
        )[0]
        surgical_profile_key = (
            f"role_prof_profile_surgical_{surgical_specialty['specialty_id']}"
        )
        at.selectbox(key=surgical_profile_key).set_value(
            surgical_profile["professional_id"]
        ).run()
        at.selectbox(key="role_variant").set_value("Clínico").run()
        self.assertNotIn(
            "role_prof_specialty_surgical", at.session_state.filtered_state
        )
        self.assertNotIn(surgical_profile_key, at.session_state.filtered_state)

    def test_changing_specialty_clears_incompatible_profile_immediately(self):
        at, first_specialty, _profile = self.select_professional_draft("clinical")
        old_key = f"role_prof_profile_clinical_{first_specialty['specialty_id']}"
        second_specialty = professional_specialty_choices("clinical")[1]
        at.selectbox(key="role_prof_specialty_clinical").set_value(
            second_specialty["specialty_id"]
        ).run()
        self.assertNotIn(old_key, at.session_state.filtered_state)
        new_key = f"role_prof_profile_clinical_{second_specialty['specialty_id']}"
        self.assertIsNone(at.selectbox(key=new_key).value)

    def test_changing_user_type_clears_professional_only_state(self):
        at, specialty, _profile = self.select_professional_draft("clinical")
        profile_key = f"role_prof_profile_clinical_{specialty['specialty_id']}"
        at.selectbox(key="role_category").set_value("Directivo").run()
        state = at.session_state.filtered_state
        self.assertNotIn("role_prof_specialty_clinical", state)
        self.assertNotIn(profile_key, state)
        self.assertNotIn("role_service_id", state)
        self.assertNotIn("role_specialty_id", state)

    def test_dashboard_and_sidebar_expose_specialty_and_readable_profile(self):
        at, specialty, profile = self.select_professional_draft("clinical")
        next(
            button for button in at.button if button.label == "Entrar al dashboard"
        ).click().run()
        text = " ".join(
            str(item.value)
            for item in [*at.caption, *at.markdown]
            if isinstance(item.value, str)
        )
        self.assertIn(specialty["display_name"], text)
        self.assertIn(profile["short_label_es"], text)
        self.assertNotIn(profile["professional_id"], text)
        self.assertIsNone(at.session_state.filtered_state["pending_navigation"])

    def test_mixed_lenses_remain_separate_without_composite(self):
        profile = professional_profiles("mixed")[0]
        contexts = {
            lens: professional_lens_context(profile, lens)
            for lens in ("clinical", "surgical")
        }
        groups = build_mixed_presentations(
            self.dataset,
            self.current,
            self.previous,
            profile["professional_id"],
            lens_contexts=contexts,
        )
        self.assertEqual(set(groups), {"clinical", "surgical"})
        ids = [card.indicator_id for group in groups.values() for card in group]
        self.assertFalse(any("combined" in indicator_id for indicator_id in ids))


if __name__ == "__main__":
    unittest.main()
