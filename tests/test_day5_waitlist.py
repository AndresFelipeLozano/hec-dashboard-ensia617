from __future__ import annotations

import copy
from datetime import date
from pathlib import Path
import sys
from time import perf_counter
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_simulated_data import generate_dataset  # noqa: E402
from hec_dashboard.app_config import load_contract  # noqa: E402
from hec_dashboard.data_ingestion import CandidateDataset, validate_tables  # noqa: E402
from hec_dashboard.indicator_engine import IndicatorContext, IndicatorEngine  # noqa: E402
from hec_dashboard.visual_analytics import (  # noqa: E402
    aging_distribution,
    hec_marker,
    origin_bubbles,
    prestation_composition,
    role_activity_composition,
    role_activity_trend,
    scoped_waitlist_rows,
    specialty_pressure,
    status_flow,
    waitlist_indicator_trend,
)
from validate_data_contract import load_simulated_tables  # noqa: E402


WAITLIST_INDICATORS = (
    "new_waitlist_open_count",
    "new_wait_median_days",
    "new_wait_p75_days",
    "new_wait_over_90_pct",
    "new_waitlist_resolution_pct",
    "followup_overdue_open_count",
    "followup_overdue_median_days",
    "followup_overdue_p75_days",
    "followup_unscheduled_pct",
    "followup_resolution_pct",
)


class Day5WaitlistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_tables = load_simulated_tables(REPO_ROOT)
        cls.report = validate_tables(
            copy.deepcopy(cls.raw_tables),
            REPO_ROOT,
            validation_timestamp_utc="2026-09-02T12:00:00+00:00",
        )
        cls.dataset = CandidateDataset(
            cls.report.metadata,
            cls.report.accepted_rows,
            cls.report.summary(),
        )
        cls.engine = IndicatorEngine.from_repo(REPO_ROOT)
        cls.q1 = (date(2026, 1, 1), date(2026, 3, 31))
        cls.q2 = (date(2026, 4, 1), date(2026, 6, 30))

    def test_contract_13_adds_governed_referral_diagnosis(self):
        contract = load_contract("data_contract")
        self.assertEqual(contract["contract_version"], "1.3.0")
        self.assertIn("1.1.0", contract["workbook"]["legacy_compatible_versions"])
        self.assertIn("1.2.0", contract["workbook"]["legacy_compatible_versions"])
        columns = [
            item["name"]
            for item in contract["sheets"]["LISTA_ESPERA_AMB"]["columns"]
        ]
        self.assertEqual(len(columns), 18)
        self.assertIn("referral_diagnosis_id", columns)
        self.assertNotIn("patient_id", columns)
        self.assertNotIn("rut", columns)

    def test_packaged_waitlist_has_exact_coverage(self):
        rows = self.dataset.tables["LISTA_ESPERA_AMB"]
        self.assertEqual(len(rows), 6240)
        counts = {}
        for row in rows:
            key = (row["specialty_id"], row["queue_type"], row["period_id"])
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(len(counts), 26 * 2 * 2)
        self.assertEqual(set(counts.values()), {60})
        self.assertEqual(len({row["wait_episode_id"] for row in rows}), 6240)
        self.assertTrue(all(row["simulated_flag"] is True for row in rows))

    def test_waitlist_temporal_and_status_semantics_are_explicit(self):
        for row in self.dataset.tables["LISTA_ESPERA_AMB"]:
            if row["queue_type"] == "new_consultation":
                self.assertIsNotNone(row["queue_entry_date"])
                self.assertIsNone(row["control_due_date"])
            else:
                self.assertIsNone(row["queue_entry_date"])
                self.assertIsNotNone(row["control_due_date"])
            if row["episode_status"] == "completed":
                self.assertIsNotNone(row["completion_date"])
                self.assertLessEqual(row["completion_date"], row["snapshot_date"])
            else:
                self.assertIsNone(row["completion_date"])
            if row["episode_status"] == "open_scheduled":
                self.assertIsNotNone(row["scheduled_date"])
            else:
                self.assertIsNone(row["scheduled_date"])
            self.assertEqual(
                row["period_id"],
                f"{row['snapshot_date'].year}-Q{((row['snapshot_date'].month - 1) // 3) + 1}",
            )

    def test_every_specialty_period_has_all_ten_indicators_available(self):
        scopes = sorted(
            {
                (row["service_id"], row["specialty_id"])
                for row in self.dataset.tables["LISTA_ESPERA_AMB"]
            }
        )
        started = perf_counter()
        for service_id, specialty_id in scopes:
            for current, previous in ((self.q2, self.q1), (self.q1, self.q2)):
                context = IndicatorContext(
                    period_start=current[0],
                    period_end=current[1],
                    previous_period_start=previous[0],
                    previous_period_end=previous[1],
                    indicator_profile="institutional",
                    service_id=service_id,
                    specialty_id=specialty_id,
                )
                for indicator_id in WAITLIST_INDICATORS:
                    result = self.engine.calculate(indicator_id, self.dataset, context)
                    self.assertEqual(
                        result.status,
                        "available",
                        (service_id, specialty_id, indicator_id, result.reason_es),
                    )
        self.assertLess(perf_counter() - started, 2.0)

    def test_every_professional_profile_has_followup_coverage(self):
        profiles = load_contract("professional_profiles")["profiles"]
        followup_ids = WAITLIST_INDICATORS[5:]
        for profile in profiles:
            indicator_profile = (
                "professional_surgical"
                if profile["profile_type"] == "surgical"
                else "professional_clinical"
            )
            context = IndicatorContext(
                period_start=self.q2[0],
                period_end=self.q2[1],
                previous_period_start=self.q1[0],
                previous_period_end=self.q1[1],
                indicator_profile=indicator_profile,
                service_id=profile["service_id"],
                specialty_id=profile["specialty_id"],
                simulated_profile_key=profile["professional_id"],
            )
            for indicator_id in followup_ids:
                result = self.engine.calculate(indicator_id, self.dataset, context)
                self.assertEqual(
                    result.status,
                    "available",
                    (profile["professional_id"], indicator_id, result.valid_n),
                )

    def test_legacy_11_load_is_accepted_and_new_indicators_are_unavailable(self):
        tables = copy.deepcopy(self.raw_tables)
        del tables["LISTA_ESPERA_AMB"]
        metadata = tables["METADATOS"]
        version_row = next(row for row in metadata if row[0] == "contract_version")
        version_row[1] = "1.1.0"
        report = validate_tables(tables, REPO_ROOT)
        self.assertTrue(report.activatable, report.structural_errors)
        self.assertEqual(report.accepted_row_count, 8960)
        legacy = CandidateDataset(report.metadata, report.accepted_rows, report.summary())
        result = self.engine.calculate("new_waitlist_open_count", legacy)
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.value)
        self.assertIn("no contiene LISTA_ESPERA_AMB", result.reason_es)

    def test_contract_12_missing_waitlist_is_structural_rejection(self):
        tables = copy.deepcopy(self.raw_tables)
        del tables["LISTA_ESPERA_AMB"]
        report = validate_tables(tables, REPO_ROOT)
        self.assertFalse(report.activatable)
        self.assertIn(
            "LISTA_ESPERA_AMB", {issue.sheet for issue in report.structural_errors}
        )

    def test_identity_column_is_rejected_structurally(self):
        tables = copy.deepcopy(self.raw_tables)
        tables["LISTA_ESPERA_AMB"][0].append("patient_rut")
        for row in tables["LISTA_ESPERA_AMB"][1:]:
            row.append("")
        report = validate_tables(tables, REPO_ROOT)
        self.assertFalse(report.activatable)
        self.assertIn("STRUCT_COLUMNS", {issue.code for issue in report.structural_errors})

    def test_invalid_waitlist_semantics_quarantine_only_the_row(self):
        tables = copy.deepcopy(self.raw_tables)
        headers = tables["LISTA_ESPERA_AMB"][0]
        row = tables["LISTA_ESPERA_AMB"][1]
        row[headers.index("episode_status")] = "completed"
        row[headers.index("completion_date")] = ""
        report = validate_tables(tables, REPO_ROOT)
        self.assertTrue(report.activatable)
        self.assertEqual(report.rejected_row_count, 1)
        self.assertIn(
            "ROW_WAITLIST_SEMANTIC_CONTRADICTION",
            {issue.code for issue in report.issues},
        )

    def test_visual_aggregates_and_map_reconcile(self):
        context = {"role_id": "director"}
        rows = scoped_waitlist_rows(self.dataset, self.q2, context)
        self.assertEqual(len(rows), 3120)
        self.assertEqual(sum(item["Episodios"] for item in status_flow(rows)), 3120)
        open_count = sum(row["episode_status"].startswith("open_") for row in rows)
        self.assertEqual(
            sum(item["Episodios"] for item in aging_distribution(rows)), open_count
        )
        self.assertEqual(
            sum(item["Episodios"] for item in prestation_composition(rows)), 3120
        )
        self.assertEqual(len(specialty_pressure(rows)), 26)
        bubbles = origin_bubbles(self.dataset, self.q2, self.q1, context)
        self.assertEqual(sum(item["Episodios"] for item in bubbles), 3120)
        self.assertAlmostEqual(sum(item["Participación (%)"] for item in bubbles), 100.0, delta=0.1)
        self.assertTrue(all(item["Episodios"] >= 10 for item in bubbles))
        self.assertTrue(
            all(
                item["Especialidad seleccionada"] == "Todas las especialidades"
                and item["Prestación principal"]
                for item in bubbles
            )
        )
        filtered_context = {"role_id": "director", "prestation_type": "consulta_nueva"}
        filtered = origin_bubbles(self.dataset, self.q2, self.q1, filtered_context)
        expected_filtered = len(scoped_waitlist_rows(self.dataset, self.q2, filtered_context))
        self.assertEqual(sum(item["Episodios"] for item in filtered), expected_filtered)
        self.assertTrue(all(item["Prestación principal"] == "Consulta nueva" for item in filtered))
        self.assertEqual(hec_marker()["Código DEIS"], "111101")

    def test_governed_waitlist_trends_use_indicator_results(self):
        rows = waitlist_indicator_trend(
            self.dataset, self.q2, self.q1, {"role_id": "director"}
        )
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row["Estado"] == "available" for row in rows))
        current_open = next(
            row["Valor"]
            for row in rows
            if row["Período"] == "Actual"
            and row["Indicador"] == "Consultas nuevas pendientes"
        )
        expected = self.engine.calculate(
            "new_waitlist_open_count",
            self.dataset,
            IndicatorContext(
                period_start=self.q2[0],
                period_end=self.q2[1],
                previous_period_start=self.q1[0],
                previous_period_end=self.q1[1],
                indicator_profile="institutional",
            ),
        )
        self.assertEqual(current_open, expected.value)

    def test_role_activity_charts_reconcile_and_mixed_lenses_are_isolated(self):
        director = {"role_id": "director"}
        trend = role_activity_trend(self.dataset, self.q2, self.q1, director)
        current_referrals = next(
            row["Eventos"]
            for row in trend
            if row["Período"] == "Actual"
            and row["Serie"] == "Demanda ambulatoria derivada"
        )
        expected_referrals = sum(
            self.q2[0] <= row["period_date"] <= self.q2[1]
            for row in self.dataset.tables["DERIVACIONES"]
        )
        self.assertEqual(current_referrals, expected_referrals)
        self.assertEqual(
            sum(row["Eventos"] for row in role_activity_composition(self.dataset, self.q2, director)),
            expected_referrals,
        )

        mixed = next(
            profile
            for profile in load_contract("professional_profiles")["profiles"]
            if profile["profile_type"] == "mixed"
        )
        base = {
            "service_id": mixed["service_id"],
            "specialty_id": mixed["specialty_id"],
            "simulated_profile_key": mixed["professional_id"],
        }
        clinical = role_activity_composition(
            self.dataset,
            self.q2,
            {**base, "role_id": "professional_clinical", "professional_lens": "clinical"},
        )
        surgical = role_activity_composition(
            self.dataset,
            self.q2,
            {**base, "role_id": "professional_surgical", "professional_lens": "surgical"},
        )
        self.assertTrue(all("Tipo de actividad" in row for row in [*clinical, *surgical]))
        self.assertNotEqual(
            {row["Tipo de actividad"] for row in clinical},
            {row["Tipo de actividad"] for row in surgical},
        )

    def test_visual_layer_contains_no_patient_level_fields(self):
        forbidden = {"rut", "patient_id", "nombre_paciente", "direccion_paciente"}
        rows = scoped_waitlist_rows(self.dataset, self.q2, {"role_id": "director"})
        self.assertTrue(rows)
        self.assertTrue(forbidden.isdisjoint(rows[0]))
        source = (
            REPO_ROOT / "dashboard" / "components" / "visuals.py"
        ).read_text(encoding="utf-8")
        self.assertIn("px.scatter_map", source)
        self.assertIn("map_style=\"carto-positron\"", source)

    def test_generation_is_deterministic_and_legacy_tables_remain_equal(self):
        first, first_metadata = generate_dataset()
        second, second_metadata = generate_dataset()
        self.assertEqual(first_metadata, second_metadata)
        self.assertEqual(first, second)
        self.assertEqual(len(first["LISTA_ESPERA_AMB"]), 6240)


if __name__ == "__main__":
    unittest.main()
