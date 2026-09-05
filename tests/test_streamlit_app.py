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
from dashboard.components.common import FOOTER_TEXT  # noqa: E402


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

    def assert_footer(self, at: AppTest) -> None:
        self.assertTrue(
            any(
                FOOTER_TEXT in item.value
                for item in at.markdown
                if isinstance(item.value, str)
            )
        )

    def test_entrypoint_loads_with_academic_simulation_disclaimer(self):
        at = self.app()
        self.assertEqual(len(at.exception), 0)
        rendered = " ".join(
            item.value for item in at.markdown if isinstance(item.value, str)
        )
        self.assertIn("Tablero de gestión HEC", rendered)
        combined = " ".join(
            item.value for item in [*at.caption, *at.info, *at.markdown]
            if isinstance(item.value, str)
        )
        self.assertIn("Demostración académica", combined)
        self.assertIn("datos completamente simulados", combined.casefold())
        self.assertEqual(len(at.get("json")), 0)
        self.assert_footer(at)

    def test_global_footer_is_shared_static_and_in_flow(self):
        source = (REPO_ROOT / "dashboard/components/common.py").read_text(
            encoding="utf-8"
        )
        app_source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn(FOOTER_TEXT, source)
        self.assertEqual(app_source.count("render_footer()"), 1)
        self.assertNotRegex(source, r"position\s*:\s*(fixed|sticky)")

    def test_footer_is_present_on_every_registered_page(self):
        landing = self.app()
        self.assert_footer(landing)
        self.assert_footer(self.open_callable_page(landing, "carga"))
        self.assert_footer(self.open_callable_page(landing, "calidad"))
        dashboard = self.select_role("Directivo", "Director")
        self.assert_footer(self.open_callable_page(dashboard, "dashboard"))

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

    def test_director_prototype_has_role_tabs_and_isolated_inpatient_history(self):
        at = self.select_role("Directivo", "Director")
        self.open_callable_page(at, "dashboard")
        self.assertEqual(
            [item.label for item in at.get("tab")],
            [
                "Resumen ejecutivo",
                "Acceso ambulatorio",
                "Hospitalización",
                "Red territorial",
                "Métodos y calidad",
            ],
        )
        self.assertIn("Hospitalización y camas", [item.value for item in at.subheader])
        inpatient_selector = at.selectbox(key="inpatient_trend_director")
        self.assertEqual(inpatient_selector.value, "inpatient_occupancy_pct")
        rendered = " ".join(
            item.value for item in at.markdown if isinstance(item.value, str)
        )
        self.assertIn("Curated inpatient reference — 2025", rendered)
        self.assertIn("Período fijo: enero–diciembre de 2025", rendered)
        self.assertIn("Referencia descriptiva · sin meta ni delta", rendered)
        self.assertNotIn("Curated inpatient reference — Q2 2026", rendered)
        inpatient_cards = next(
            item.value
            for item in at.markdown
            if isinstance(item.value, str) and "Ocupación de camas" in item.value
        )
        self.assertEqual(inpatient_cards.count('class="hec-metric-card"'), 4)

    def test_non_directorial_dashboard_does_not_invoke_inpatient_component(self):
        at = self.select_role("Jefe de Servicio", "Clínico")
        self.open_callable_page(at, "dashboard")
        self.assertNotIn("Hospitalización y camas", [item.value for item in at.subheader])
        self.assertFalse(
            any(
                item.key and item.key.startswith("inpatient_trend_")
                for item in at.selectbox
            )
        )

    def test_palliative_prototype_is_service_level_with_publishable_map(self):
        at = self.app()
        at.selectbox(key="role_category").set_value("Jefe de Servicio").run()
        at.selectbox(key="role_variant").set_value("Clínico").run()
        at.selectbox(key="role_service_id").set_value(
            "alivio_dolor_cuidados_paliativos"
        ).run()
        self.assertNotIn("role_specialty_id", [item.key for item in at.selectbox])
        next(button for button in at.button if button.label == "Entrar al dashboard").click().run()
        self.open_callable_page(at, "dashboard")
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(
            [item.label for item in at.get("tab")],
            [
                "Resumen del servicio",
                "Comparación ambulatoria",
                "Origen territorial",
                "Datos y métodos",
            ],
        )
        self.assertTrue(
            any(
                item.id.endswith("-palliative_service_origin_map")
                for item in at.get("plotly_chart")
            )
        )
        content = " ".join(
            item.value
            for item in [*at.markdown, *at.caption, *at.info]
            if isinstance(item.value, str)
        )
        self.assertIn("Derivaciones al servicio", content)
        self.assertIn("no a una especialidad ni a un profesional", content)
        self.assertNotIn("No publicable", content)

    def test_diabetology_prototype_has_bounded_role_specific_tabs(self):
        at = self.app()
        at.selectbox(key="role_category").set_value("Profesional").run()
        at.selectbox(key="role_variant").set_value("Clínico").run()
        at.selectbox(key="role_prof_specialty_clinical").set_value(
            "diabetologia"
        ).run()
        at.selectbox(key="role_prof_profile_clinical_diabetologia").set_value(
            "SIM-PROF-C-DIABETOLOGIA-A"
        ).run()
        next(button for button in at.button if button.label == "Entrar al dashboard").click().run()
        self.open_callable_page(at, "dashboard")
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(
            [item.label for item in at.get("tab")],
            [
                "Resumen clínico",
                "Actividad comparada",
                "Origen de la demanda",
                "Datos y métodos",
            ],
        )
        rendered = " ".join(
            item.value
            for item in [*at.markdown, *at.caption, *at.info]
            if isinstance(item.value, str)
        )
        self.assertIn("no constituyen ranking", rendered.casefold())
        self.assertIn("No atribuye derivaciones", rendered)

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
        self.assertIn("hec-sim-day5-v1", content)
        self.assertIn("Contrato", content)
        self.assertGreaterEqual(len(at.metric), 5)
        tables = " ".join(str(item.value) for item in at.table)
        self.assertIn("Hoja LISTA_ESPERA_AMB presente", tables)
        self.assertIn("Inconsistencias de cronología", tables)
        self.assertIn("Catálogo DEIS empaquetado", tables)
        self.assertIn("55 de 55", tables)
        self.assertIn("Orígenes DEIS con coordenadas completas", tables)
        self.assertIn("Indicadores no disponibles por carga legado 1.1", tables)
        self.assertIn("Registros de origen interno (HEC)", tables)
        self.assertIn("Origen interno HEC · LISTA_ESPERA_AMB", tables)
        self.assertIn("Consulta nueva", tables)
        self.assertIn("Control", tables)

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
