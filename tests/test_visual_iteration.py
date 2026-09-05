from __future__ import annotations

import copy
from collections import Counter
from datetime import date
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from hec_dashboard.app_config import load_contract  # noqa: E402
from hec_dashboard.data_ingestion import CandidateDataset, validate_tables  # noqa: E402
from hec_dashboard.visual_analytics import (  # noqa: E402
    aging_composition_100,
    origin_bubbles,
    role_activity_composition,
    scoped_waitlist_rows,
    service_referral_origin_summary,
    service_referral_status_composition,
    service_referral_type_composition,
    specialty_new_wait_relationship,
    status_flow_composition_100,
)
from validate_data_contract import load_simulated_tables  # noqa: E402


Q1 = (date(2026, 1, 1), date(2026, 3, 31))
Q2 = (date(2026, 4, 1), date(2026, 6, 30))
PALLIATIVE = {
    "role_id": "service_chief_clinical",
    "service_id": "alivio_dolor_cuidados_paliativos",
    "specialty_id": None,
}
DIABETOLOGY = {
    "role_id": "professional_clinical",
    "service_id": "especialidades_medicas_adulto",
    "specialty_id": "diabetologia",
    "simulated_profile_key": "SIM-PROF-C-DIABETOLOGIA-A",
    "professional_lens": "clinical",
}


class VisualIterationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = load_simulated_tables(REPO_ROOT)
        cls.report = validate_tables(copy.deepcopy(cls.raw), REPO_ROOT)
        cls.dataset = CandidateDataset(
            cls.report.metadata,
            cls.report.accepted_rows,
            cls.report.summary(),
        )

    def test_packaged_dataset_is_unchanged_and_fully_accepted(self):
        self.assertEqual(self.report.accepted_row_count, 15200)
        self.assertEqual(self.report.rejected_row_count, 0)
        self.assertTrue(self.report.activatable)

    def test_aging_and_flow_compositions_reconcile_to_source_rows(self):
        source = scoped_waitlist_rows(self.dataset, Q2, {"role_id": "director"})
        open_count = sum(
            row["episode_status"] in {"open_unscheduled", "open_scheduled"}
            for row in source
        )
        aging = aging_composition_100(source)
        flow = status_flow_composition_100(source)
        self.assertEqual(sum(row["Episodios"] for row in aging), open_count)
        self.assertEqual(sum(row["Episodios"] for row in flow), len(source))
        for composition in (aging, flow):
            totals = Counter()
            for row in composition:
                totals[row["Cola"]] += row["Porcentaje"]
            self.assertTrue(all(abs(value - 100) <= 0.02 for value in totals.values()))

    def test_director_relationship_is_specialty_aggregate_not_person_level(self):
        rows = specialty_new_wait_relationship(
            self.dataset, Q2, {"role_id": "director"}
        )
        self.assertEqual(len(rows), 26)
        self.assertTrue(all(row["Abiertos"] >= 30 for row in rows))
        self.assertTrue(
            all(
                set(row)
                == {
                    "Especialidad",
                    "Consultas nuevas",
                    "Abiertos",
                    "P75 espera (días)",
                }
                for row in rows
            )
        )

    def test_directorial_specialty_composition_uses_readable_governed_labels(self):
        rows = role_activity_composition(
            self.dataset, Q2, {"role_id": "medical_director"}
        )
        labels = [row["Especialidad"] for row in rows]
        self.assertIn("Servicios sin especialidad analítica", labels)
        self.assertNotIn(None, labels)
        self.assertTrue(all("_" not in label for label in labels))
        self.assertEqual(sum(row["Eventos"] for row in rows), 1696)

    def test_palliative_service_has_no_governed_analytical_specialty(self):
        specialties = load_contract("services")["analytical_specialties"]
        self.assertFalse(
            any(
                item.get("parent_unit_id") == PALLIATIVE["service_id"]
                or item.get("service_id") == PALLIATIVE["service_id"]
                for item in specialties
            )
        )

    def test_palliative_territory_preserves_n10_and_is_publishable_in_both_periods(self):
        summary = service_referral_origin_summary(
            self.dataset, Q2, Q1, PALLIATIVE
        )
        self.assertEqual(summary["source"], "DERIVACIONES")
        self.assertEqual(summary["service_referrals"], 91)
        self.assertEqual(summary["origin_cells"], 7)
        self.assertEqual(summary["publishable_cells"], 5)
        self.assertEqual(summary["suppressed_cell_count"], 2)
        self.assertEqual(summary["minimum_cell_n"], 10)
        self.assertTrue(all(row["Episodios"] >= 10 for row in summary["rows"]))
        prior = service_referral_origin_summary(
            self.dataset, Q1, Q2, PALLIATIVE
        )
        self.assertEqual(prior["publishable_cells"], 5)
        self.assertTrue(all(row["Episodios"] >= 10 for row in prior["rows"]))
        fallback = service_referral_status_composition(self.dataset, Q2, PALLIATIVE)
        self.assertEqual(sum(row["Derivaciones"] for row in fallback), 91)

    def test_palliative_type_and_status_breakdowns_are_distinct_and_reconcile(self):
        types = service_referral_type_composition(self.dataset, Q2, PALLIATIVE)
        statuses = service_referral_status_composition(self.dataset, Q2, PALLIATIVE)
        self.assertEqual(sum(row["Derivaciones"] for row in types), 91)
        self.assertEqual(sum(row["Derivaciones"] for row in statuses), 91)
        self.assertNotEqual(set(types[0]), set(statuses[0]))

    def test_diabetology_demand_origin_preserves_suppression_and_no_attribution(self):
        rows = origin_bubbles(self.dataset, Q2, Q1, DIABETOLOGY)
        self.assertTrue(rows)
        self.assertTrue(all(row["Episodios"] >= 10 for row in rows))
        forbidden = {
            "patient_id",
            "patient_name",
            "rut",
            "professional_id",
            "simulated_profile_key",
        }
        self.assertTrue(all(not (set(row) & forbidden) for row in rows))

    def test_bounded_prototype_does_not_expand_inpatient_to_medical_director(self):
        source = (REPO_ROOT / "dashboard/views/role_dashboard.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(source.count('render_inpatient_reference("director")'), 1)
        self.assertNotIn('render_inpatient_reference("medical_director")', source)


if __name__ == "__main__":
    unittest.main()
