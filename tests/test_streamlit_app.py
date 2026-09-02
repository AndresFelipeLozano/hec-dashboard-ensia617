from __future__ import annotations

from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from streamlit.testing.v1 import AppTest  # noqa: E402
from streamlit.util import calc_hash  # noqa: E402

from hec_dashboard.app_config import (  # noqa: E402
    professional_profiles,
    professional_specialty_choices,
    service_choices,
)


class StreamlitAppTests(unittest.TestCase):
    def app(self) -> AppTest:
        return AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=20).run()

    def select_role(self, category: str, variant: str) -> AppTest:
        at = self.app()
        at.selectbox(key="role_category").set_value(category).run()
        at.selectbox(key="role_variant").set_value(variant).run()
        if category == "Profesional":
            profile_type = {
                "Clínico": "clinical",
                "Quirúrgico": "surgical",
                "Mixto": "mixed",
            }[variant]
            specialty_id = professional_specialty_choices(profile_type)[0][
                "specialty_id"
            ]
            at.selectbox(key=f"role_prof_specialty_{profile_type}").set_value(
                specialty_id
            ).run()
            profile = professional_profiles(profile_type, specialty_id)[0]
            at.selectbox(
                key=f"role_prof_profile_{profile_type}_{specialty_id}"
            ).set_value(profile["professional_id"]).run()
        entry = next(button for button in at.button if button.label == "Entrar al dashboard")
        entry.click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertIsNone(at.session_state.filtered_state["pending_navigation"])
        self.assertNotIn(
            "Seleccione su vista de trabajo", [item.value for item in at.header]
        )
        return at

    def open_callable_page(self, at: AppTest, url_path: str) -> AppTest:
        # AppTest.switch_page targets file pages only; callable st.Page uses its URL hash.
        at._page_hash = calc_hash(url_path)
        return at.run()

    def test_entrypoint_loads_with_academic_simulation_disclaimer(self):
        at = self.app()
        self.assertEqual(len(at.exception), 0)
        self.assertIn("HEC | Apoyo a decisiones por rol", [item.value for item in at.title])
        combined = " ".join(item.value for item in [*at.caption, *at.info])
        self.assertIn("Demostración académica", combined)
        self.assertIn("Datos completamente simulados", combined)
        self.assertEqual(len(at.get("json")), 0)

    def test_reset_returns_to_landing_and_clears_role(self):
        at = self.select_role("Jefe de Servicio", "Clínico")
        reset = next(
            button
            for button in at.button
            if button.label == "Cambiar o restablecer rol"
        )
        reset.click().run()
        self.assertIsNone(at.session_state.filtered_state["role_context"])
        self.assertIn(
            "Seleccione su vista de trabajo", [item.value for item in at.header]
        )

    def test_initial_state_has_no_false_authenticated_role(self):
        at = self.app()
        self.assertIsNone(at.session_state.filtered_state["role_context"])
        self.assertIn("Rol no seleccionado", " ".join(item.value for item in at.markdown))
        self.assertNotIn("autenticado", " ".join(item.value for item in at.markdown).lower())

    def test_director_workflow_opens_institutional_dashboard(self):
        at = self.select_role("Directivo", "Director")
        self.assertEqual(at.session_state.filtered_state["role_context"]["role_id"], "director")
        self.open_callable_page(at, "dashboard")
        self.assertEqual(len(at.exception), 0)
        self.assertIn("Visión institucional — Director", [item.value for item in at.header])
        self.assertLessEqual(len(at.metric), 6)

    def test_medical_director_is_distinct(self):
        at = self.select_role("Directivo", "Director Médico")
        self.assertEqual(
            at.session_state.filtered_state["role_context"]["role_id"],
            "medical_director",
        )

    def test_clinical_service_chief_uses_allowed_clinical_service(self):
        at = self.select_role("Jefe de Servicio", "Clínico")
        context = at.session_state.filtered_state["role_context"]
        allowed = {item["unit_id"] for item in service_choices("clinical")}
        self.assertEqual(context["role_id"], "service_chief_clinical")
        self.assertIn(context["service_id"], allowed)
        self.assertEqual(context["dashboard_type"], "clinical")

    def test_surgical_service_chief_uses_allowed_surgical_service(self):
        at = self.select_role("Jefe de Servicio", "Quirúrgico")
        context = at.session_state.filtered_state["role_context"]
        allowed = {item["unit_id"] for item in service_choices("surgical")}
        self.assertEqual(context["role_id"], "service_chief_surgical")
        self.assertIn(context["service_id"], allowed)
        self.assertEqual(context["dashboard_type"], "surgical")

    def test_clinical_professional_has_explicit_clinical_lens(self):
        at = self.select_role("Profesional", "Clínico")
        context = at.session_state.filtered_state["role_context"]
        self.assertEqual(context["role_id"], "professional_clinical")
        self.assertEqual(context["professional_lens"], "clinical")
        self.assertTrue(context["simulated_profile_key"].startswith("SIM-"))
        self.assertTrue(context["specialty_id"])
        self.assertTrue(context["specialty_display_name"])
        self.assertNotEqual(
            context["professional_display_label"], context["professional_id"]
        )

    def test_surgical_professional_has_explicit_surgical_lens(self):
        at = self.select_role("Profesional", "Quirúrgico")
        context = at.session_state.filtered_state["role_context"]
        self.assertEqual(context["role_id"], "professional_surgical")
        self.assertEqual(context["professional_lens"], "surgical")
        self.assertTrue(context["simulated_profile_key"].startswith("SIM-"))
        self.assertTrue(context["specialty_id"])

    def test_mixed_dashboard_has_separate_lenses_and_no_combined_score(self):
        at = self.select_role("Profesional", "Mixto")
        context = at.session_state.filtered_state["role_context"]
        self.assertEqual(context["professional_lenses"], ["clinical", "surgical"])
        self.assertEqual(context["specialty_id"], "cirugia_pediatrica")
        self.assertEqual(context["specialty_display_name"], "Cirugía Pediátrica")
        self.open_callable_page(at, "dashboard")
        lens = at.radio(key="dashboard_mixed_lens")
        self.assertEqual(
            lens.options,
            [
                "Actividad ambulatoria/clínica",
                "Actividad quirúrgica/procedimental",
            ],
        )
        self.assertEqual(lens.value, "clinical")
        self.assertIn(
            "Actividad ambulatoria/clínica · Cirugía Pediátrica",
            [item.value for item in at.subheader],
        )
        shared_before = (
            context["professional_id"],
            context["service_id"],
            context["specialty_id"],
        )
        lens.set_value("surgical").run()
        context_after = at.session_state.filtered_state["role_context"]
        self.assertEqual(
            shared_before,
            (
                context_after["professional_id"],
                context_after["service_id"],
                context_after["specialty_id"],
            ),
        )
        self.assertIn(
            "Actividad quirúrgica/procedimental · Cirugía Pediátrica",
            [item.value for item in at.subheader],
        )
        content = " ".join(
            item.value
            for item in [*at.caption, *at.markdown, *at.info]
            if isinstance(item.value, str)
        )
        self.assertIn("No se calcula ni presenta un puntaje combinado", content)
        self.assertNotIn("Puntaje combinado:", content)

    def test_reset_mixed_role_clears_lens_state(self):
        at = self.select_role("Profesional", "Mixto")
        self.open_callable_page(at, "dashboard")
        at.radio(key="dashboard_mixed_lens").set_value("surgical").run()
        reset = next(
            button
            for button in at.button
            if button.label == "Cambiar o restablecer rol"
        )
        reset.click().run()
        self.assertIsNone(at.session_state.filtered_state["role_context"])
        self.assertNotIn("dashboard_mixed_lens", at.session_state.filtered_state)

    def test_responsive_shell_uses_adaptive_width_controls(self):
        app_source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        landing_source = (REPO_ROOT / "dashboard/views/landing.py").read_text(
            encoding="utf-8"
        )
        common_source = (REPO_ROOT / "dashboard/components/common.py").read_text(
            encoding="utf-8"
        )
        dashboard_source = (
            REPO_ROOT / "dashboard/views/role_dashboard.py"
        ).read_text(encoding="utf-8")
        self.assertIn('initial_sidebar_state="auto"', app_source)
        self.assertIn("use_container_width=True", landing_source)
        self.assertIn("use_container_width=True", common_source)
        self.assertIn("horizontal=False", dashboard_source)

    def test_upload_page_has_download_and_invalid_candidate_preserves_active(self):
        at = self.app()
        active = at.session_state.filtered_state["active_dataset"]
        self.open_callable_page(at, "carga")
        self.assertEqual(len(at.download_button), 1)
        self.assertEqual(len(at.file_uploader), 1)
        at.file_uploader[0].set_value(
            (
                "invalid.xlsx",
                b"not-an-xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        ).run()
        validate = next(button for button in at.button if button.label == "Validar candidato")
        validate.click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertIs(
            at.session_state.filtered_state["active_dataset"],
            active,
        )
        self.assertIsNone(at.session_state.filtered_state["candidate_dataset"])
        self.assertTrue(any("conservó" in item.value for item in at.error))

    def test_data_quality_page_shows_active_bundled_dataset(self):
        at = self.app()
        self.open_callable_page(at, "calidad")
        self.assertEqual(len(at.exception), 0)
        content = " ".join(
            item.value for item in at.markdown if isinstance(item.value, str)
        )
        self.assertIn("hec-sim-day4r-v2", content)
        self.assertIn("Contrato", content)
        self.assertGreaterEqual(len(at.metric), 5)

    def test_ui_exposes_no_real_person_labels(self):
        at = self.select_role("Profesional", "Mixto")
        content = " ".join(
            str(item.value)
            for item in [*at.markdown, *at.caption, *at.info]
        )
        self.assertNotIn("RUT", content)
        self.assertNotIn("nombre del profesional", content.lower())
        self.assertTrue(
            at.session_state.filtered_state["role_context"][
                "simulated_profile_key"
            ].startswith("SIM-")
        )


if __name__ == "__main__":
    unittest.main()
