from __future__ import annotations

import copy
import csv
from collections import Counter
from datetime import date
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
import zipfile
from xml.etree import ElementTree


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from hec_dashboard.app_config import load_contract, referral_diagnoses  # noqa: E402
from hec_dashboard.data_ingestion import CandidateDataset, validate_tables  # noqa: E402
from dashboard.views.data_quality import _day5_quality_metrics  # noqa: E402
from hec_dashboard.visual_analytics import (  # noqa: E402
    HEC_DEIS_CODE,
    HEC_MARKER_SIZE,
    HEC_MARKER_SYMBOL,
    center_waitlist_context,
    diagnosis_composition_by_establishment,
    diagnosis_options,
    hec_marker,
    map_cache_key,
    map_signature,
    origin_bubbles,
    referring_center_diagnoses,
    referring_center_prestations,
    referring_center_specialties,
    rows_to_csv,
    scoped_network_rows,
    scoped_waitlist_rows,
)
from validate_data_contract import load_simulated_tables  # noqa: E402


Q1 = (date(2026, 1, 1), date(2026, 3, 31))
Q2 = (date(2026, 4, 1), date(2026, 6, 30))


class Day5MapRemediationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = load_simulated_tables(REPO_ROOT)
        cls.report = validate_tables(copy.deepcopy(cls.raw), REPO_ROOT)
        cls.dataset = CandidateDataset(
            cls.report.metadata, cls.report.accepted_rows, cls.report.summary()
        )
        cls.catalog = referral_diagnoses(repo_root=REPO_ROOT)

    def context(self, specialty_id: str | None = None, **extra):
        value = {"role_id": "director", "specialty_id": specialty_id}
        value.update(extra)
        return value

    def test_diagnosis_catalog_ids_are_unique(self):
        ids = [item["diagnosis_group_id"] for item in self.catalog]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_diagnosis_has_one_compatible_specialty(self):
        specialty_ids = {
            item["specialty_id"]
            for item in load_contract("services")["analytical_specialties"]
            if item.get("mvp_enabled")
        }
        self.assertTrue(all(item["specialty_id"] in specialty_ids for item in self.catalog))
        counts = Counter(item["specialty_id"] for item in self.catalog)
        self.assertTrue(all(counts[value] >= 4 for value in specialty_ids))

    def test_every_operational_diagnosis_exists_in_catalog(self):
        catalog_ids = {item["diagnosis_group_id"] for item in self.catalog}
        operational = {
            row["referral_diagnosis_id"]
            for row in self.dataset.tables["LISTA_ESPERA_AMB"]
        }
        self.assertTrue(operational)
        self.assertLessEqual(operational, catalog_ids)

    def test_cross_specialty_diagnosis_is_quarantined(self):
        tables = copy.deepcopy(self.raw)
        header = tables["LISTA_ESPERA_AMB"][0]
        specialty = header.index("specialty_id")
        diagnosis = header.index("referral_diagnosis_id")
        row = tables["LISTA_ESPERA_AMB"][1]
        foreign = next(
            item for item in self.catalog if item["specialty_id"] != row[specialty]
        )
        row[diagnosis] = foreign["diagnosis_group_id"]
        report = validate_tables(tables, REPO_ROOT)
        self.assertEqual(report.rejected_row_count, 1)
        self.assertIn(
            "ROW_DIAGNOSIS_SPECIALTY_MISMATCH",
            {issue.code for issue in report.issues},
        )

    def test_unknown_diagnosis_is_quarantined(self):
        tables = copy.deepcopy(self.raw)
        header = tables["LISTA_ESPERA_AMB"][0]
        tables["LISTA_ESPERA_AMB"][1][header.index("referral_diagnosis_id")] = (
            "rd_unknown_01"
        )
        report = validate_tables(tables, REPO_ROOT)
        self.assertEqual(report.rejected_row_count, 1)
        self.assertIn("ROW_INVALID_REFERRAL_DIAGNOSIS", {i.code for i in report.issues})

    def test_legacy_12_without_diagnosis_remains_compatible(self):
        tables = copy.deepcopy(self.raw)
        metadata = tables["METADATOS"]
        next(row for row in metadata if row[0] == "contract_version")[1] = "1.2.0"
        header = tables["LISTA_ESPERA_AMB"][0]
        index = header.index("referral_diagnosis_id")
        for row in tables["LISTA_ESPERA_AMB"]:
            del row[index]
        report = validate_tables(tables, REPO_ROOT)
        self.assertTrue(report.activatable, report.structural_errors)
        self.assertEqual(report.accepted_row_count, 15200)
        self.assertTrue(
            all(
                row["referral_diagnosis_id"] is None
                for row in report.accepted_rows["LISTA_ESPERA_AMB"]
            )
        )

    def test_legacy_11_remains_compatible(self):
        tables = copy.deepcopy(self.raw)
        next(row for row in tables["METADATOS"] if row[0] == "contract_version")[1] = "1.1.0"
        del tables["LISTA_ESPERA_AMB"]
        report = validate_tables(tables, REPO_ROOT)
        self.assertTrue(report.activatable)
        self.assertEqual(report.accepted_row_count, 8960)

    def test_legacy_diagnosis_absence_is_unavailable_not_zero(self):
        tables = copy.deepcopy(self.raw)
        next(row for row in tables["METADATOS"] if row[0] == "contract_version")[1] = "1.2.0"
        index = tables["LISTA_ESPERA_AMB"][0].index("referral_diagnosis_id")
        for row in tables["LISTA_ESPERA_AMB"]:
            del row[index]
        report = validate_tables(tables, REPO_ROOT)
        legacy = CandidateDataset(report.metadata, report.accepted_rows, report.summary())
        rows = scoped_waitlist_rows(legacy, Q2, self.context("urologia"))
        self.assertEqual(diagnosis_options(rows), [])
        bubbles = origin_bubbles(legacy, Q2, Q1, self.context("urologia"))
        self.assertTrue(
            all(
                row["Diagnóstico predominante"] == "No disponible en carga heredada"
                for row in bubbles
            )
        )

    def test_selected_specialty_changes_underlying_rows(self):
        urology = scoped_waitlist_rows(self.dataset, Q2, self.context("urologia"))
        neurology = scoped_waitlist_rows(
            self.dataset, Q2, self.context("neurologia_infantil")
        )
        self.assertTrue(urology and neurology)
        self.assertTrue(all(row["specialty_id"] == "urologia" for row in urology))
        self.assertNotEqual(
            {row["wait_episode_id"] for row in urology},
            {row["wait_episode_id"] for row in neurology},
        )

    def test_selected_specialty_changes_bubble_size_vector(self):
        vectors = []
        for specialty_id in (
            "urologia",
            "neurologia_infantil",
            "cardiologia_adulto",
            "cirugia_general",
            "traumatologia",
        ):
            vectors.append(
                tuple(
                    row["Episodios"]
                    for row in origin_bubbles(
                        self.dataset, Q2, Q1, self.context(specialty_id)
                    )
                )
            )
        self.assertEqual(len(vectors), len(set(vectors)))

    def test_materially_different_specialties_change_top_three(self):
        urology = origin_bubbles(self.dataset, Q2, Q1, self.context("urologia"))
        neurology = origin_bubbles(
            self.dataset, Q2, Q1, self.context("neurologia_infantil")
        )
        self.assertLessEqual(
            len(
                {row["Código DEIS"] for row in urology[:3]}
                & {row["Código DEIS"] for row in neurology[:3]}
            ),
            1,
        )

    def test_role_context_changes_map_aggregation(self):
        director = origin_bubbles(self.dataset, Q2, Q1, {"role_id": "director"})
        chief_context = {
            "role_id": "service_chief_clinical",
            "service_id": "especialidades_pediatricas",
            "specialty_id": "neurologia_infantil",
        }
        chief = origin_bubbles(self.dataset, Q2, Q1, chief_context)
        self.assertEqual(sum(row["Episodios"] for row in director), 3120)
        self.assertEqual(sum(row["Episodios"] for row in chief), 120)

    def test_diagnosis_selection_changes_bubble_sizes(self):
        context = self.context("urologia")
        unfiltered = origin_bubbles(self.dataset, Q2, Q1, context)
        diagnosis_id = diagnosis_options(
            scoped_waitlist_rows(self.dataset, Q2, context)
        )[0]["diagnosis_group_id"]
        filtered = origin_bubbles(
            self.dataset,
            Q2,
            Q1,
            {**context, "referral_diagnosis_id": diagnosis_id},
        )
        self.assertNotEqual(
            [(row["Código DEIS"], row["Episodios"]) for row in unfiltered],
            [(row["Código DEIS"], row["Episodios"]) for row in filtered],
        )

    def test_selected_center_totals_reconcile_with_map(self):
        context = self.context("urologia")
        bubbles = origin_bubbles(self.dataset, Q2, Q1, context)
        center = bubbles[0]["Código DEIS"]
        raw = [
            row
            for row in scoped_waitlist_rows(self.dataset, Q2, context)
            if row["origin_deis_code"] == center
        ]
        self.assertEqual(bubbles[0]["Episodios"], len(raw))

    def test_selected_center_specialties_reconcile_with_institutional_total(self):
        overview = origin_bubbles(self.dataset, Q2, Q1, {"role_id": "director"})
        center = overview[0]["Código DEIS"]
        breakdown = referring_center_specialties(
            self.dataset, Q2, Q1, {"role_id": "director"}, center
        )
        self.assertEqual(sum(row["Actual"] for row in breakdown), overview[0]["Episodios"])

    def test_selected_center_diagnoses_reconcile_with_specialty_total(self):
        context = self.context("urologia")
        bubbles = origin_bubbles(self.dataset, Q2, Q1, context)
        center = bubbles[0]["Código DEIS"]
        breakdown = referring_center_diagnoses(
            self.dataset, Q2, context, center
        )
        self.assertEqual(sum(row["Episodios"] for row in breakdown), bubbles[0]["Episodios"])

    def test_dominant_specialty_is_calculated_from_filtered_rows(self):
        overview = origin_bubbles(self.dataset, Q2, Q1, {"role_id": "director"})
        row = overview[0]
        raw = [
            item
            for item in scoped_waitlist_rows(self.dataset, Q2, {"role_id": "director"})
            if item["origin_deis_code"] == row["Código DEIS"]
        ]
        dominant_id = sorted(
            Counter(item["specialty_id"] for item in raw).items(),
            key=lambda item: (-item[1], item[0]),
        )[0][0]
        labels = {
            item["specialty_id"]: item["display_name"]
            for item in load_contract("services")["analytical_specialties"]
        }
        self.assertEqual(row["Especialidad predominante"], labels[dominant_id])

    def test_dominant_diagnosis_is_calculated_from_filtered_rows(self):
        context = self.context("urologia")
        row = origin_bubbles(self.dataset, Q2, Q1, context)[0]
        raw = [
            item
            for item in scoped_waitlist_rows(self.dataset, Q2, context)
            if item["origin_deis_code"] == row["Código DEIS"]
        ]
        diagnosis_id = sorted(
            Counter(item["referral_diagnosis_id"] for item in raw).items(),
            key=lambda item: (-item[1], item[0]),
        )[0][0]
        label = next(
            item["label_es"] for item in self.catalog if item["diagnosis_group_id"] == diagnosis_id
        )
        self.assertEqual(row["Diagnóstico predominante"], label)

    def test_period_variation_is_calculated_from_q1_and_q2(self):
        context = self.context("urologia")
        row = origin_bubbles(self.dataset, Q2, Q1, context)[0]
        current = sum(
            item["origin_deis_code"] == row["Código DEIS"]
            for item in scoped_waitlist_rows(self.dataset, Q2, context)
        )
        previous = sum(
            item["origin_deis_code"] == row["Código DEIS"]
            for item in scoped_waitlist_rows(self.dataset, Q1, context)
        )
        self.assertEqual(row["Variación"], current - previous)

    def test_zero_volume_centers_do_not_receive_bubbles(self):
        context = self.context("urologia")
        bubbles = origin_bubbles(self.dataset, Q2, Q1, context)
        plotted = {row["Código DEIS"] for row in bubbles}
        all_codes = {
            row["origin_deis_code"]
            for row in self.dataset.tables["LISTA_ESPERA_AMB"]
        }
        self.assertTrue(all_codes - plotted)
        self.assertTrue(all(row["Episodios"] > 0 for row in bubbles))

    def test_no_invalid_coordinate_becomes_zero_zero(self):
        for row in origin_bubbles(self.dataset, Q2, Q1, {"role_id": "director"}):
            self.assertNotEqual((row["Latitud"], row["Longitud"]), (0.0, 0.0))

    def test_hec_marker_remains_distinct(self):
        marker = hec_marker()
        self.assertEqual(marker["Código DEIS"], "111101")
        self.assertIn("Hospital", marker["Establecimiento"])
        self.assertEqual(HEC_MARKER_SIZE, 18)
        self.assertEqual(HEC_MARKER_SYMBOL, "hospital")
        self.assertNotEqual((marker["Latitud"], marker["Longitud"]), (0.0, 0.0))

    def test_packaged_external_origins_never_use_hec(self):
        fields = {
            "DERIVACIONES": "origin_establishment_code",
            "CIRUGIAS": "origin_establishment_code",
            "ACTIVIDAD_PROF": "origin_establishment_code",
            "LISTA_ESPERA_AMB": "origin_deis_code",
        }
        for sheet, field in fields.items():
            with self.subTest(sheet=sheet):
                self.assertFalse(
                    any(
                        str(row.get(field)) == HEC_DEIS_CODE
                        for row in self.dataset.tables[sheet]
                    )
                )

    def test_uploaded_internal_origin_is_retained_but_excluded_from_external_views(self):
        tables = copy.deepcopy(self.dataset.tables)
        injected = next(
            row
            for row in tables["LISTA_ESPERA_AMB"]
            if Q2[0] <= row["snapshot_date"] <= Q2[1]
        )
        injected["origin_deis_code"] = HEC_DEIS_CODE
        candidate = CandidateDataset(
            self.dataset.metadata,
            tables,
            self.dataset.validation_summary,
        )
        all_rows = scoped_waitlist_rows(candidate, Q2, {"role_id": "director"})
        external_rows = scoped_network_rows(candidate, Q2, {"role_id": "director"})
        self.assertEqual(sum(row["origin_deis_code"] == HEC_DEIS_CODE for row in all_rows), 1)
        self.assertFalse(any(row["origin_deis_code"] == HEC_DEIS_CODE for row in external_rows))

        bubbles = origin_bubbles(candidate, Q2, Q1, {"role_id": "director"})
        self.assertFalse(any(row["Código DEIS"] == HEC_DEIS_CODE for row in bubbles))
        accessible = [
            {key: value for key, value in row.items() if key not in {"Latitud", "Longitud"}}
            for row in bubbles
        ]
        self.assertNotIn(HEC_DEIS_CODE, rows_to_csv(accessible).decode("utf-8-sig"))
        self.assertEqual(
            referring_center_specialties(candidate, Q2, Q1, {"role_id": "director"}, HEC_DEIS_CODE),
            [],
        )
        self.assertEqual(
            referring_center_diagnoses(candidate, Q2, {"role_id": "director"}, HEC_DEIS_CODE),
            [],
        )
        self.assertEqual(
            referring_center_prestations(candidate, Q2, {"role_id": "director"}, HEC_DEIS_CODE),
            [],
        )
        self.assertEqual(
            center_waitlist_context(candidate, Q2, {"role_id": "director"}, HEC_DEIS_CODE),
            [],
        )

    def test_quality_classifies_internal_origins_across_all_origin_tables(self):
        tables = copy.deepcopy(self.dataset.tables)
        fields = {
            "DERIVACIONES": "origin_establishment_code",
            "CIRUGIAS": "origin_establishment_code",
            "ACTIVIDAD_PROF": "origin_establishment_code",
            "LISTA_ESPERA_AMB": "origin_deis_code",
        }
        for sheet, field in fields.items():
            tables[sheet][0][field] = HEC_DEIS_CODE
        candidate = CandidateDataset(
            self.dataset.metadata,
            tables,
            self.dataset.validation_summary,
        )
        metrics = _day5_quality_metrics(
            candidate,
            candidate.metadata,
            candidate.validation_summary,
        )
        self.assertEqual(metrics["internal_origin_by_sheet"], dict.fromkeys(fields, 1))
        self.assertEqual(metrics["internal_origin_records"], 4)
        self.assertEqual(metrics["internal_waitlist_records"], 1)
        self.assertEqual(metrics["external_network_records"], 6239)

    def test_each_map_adds_one_hec_destination_trace(self):
        source = (REPO_ROOT / "dashboard/components/visuals.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(source.count('name="Hospital El Carmen"'), 2)
        self.assertEqual(source.count('"size": HEC_MARKER_SIZE'), 2)
        self.assertEqual(source.count('"symbol": HEC_MARKER_SYMBOL'), 2)

    def test_map_table_and_csv_are_identical(self):
        table = [
            {key: value for key, value in row.items() if key not in {"Latitud", "Longitud"}}
            for row in origin_bubbles(self.dataset, Q2, Q1, self.context("urologia"))
        ]
        decoded = rows_to_csv(table).decode("utf-8-sig")
        parsed = list(csv.DictReader(StringIO(decoded)))
        self.assertEqual(len(parsed), len(table))
        self.assertEqual(parsed[0]["Código DEIS"], table[0]["Código DEIS"])
        self.assertEqual(int(parsed[0]["Episodios"]), table[0]["Episodios"])

    def test_diagnosis_composition_reconciles_with_specialty_rows(self):
        context = self.context("urologia")
        composition = diagnosis_composition_by_establishment(
            self.dataset, Q2, context
        )
        self.assertLessEqual(
            sum(row["Episodios"] for row in composition),
            len(scoped_waitlist_rows(self.dataset, Q2, context)),
        )
        self.assertTrue(all(row["Episodios"] >= 10 for row in composition))

    def test_no_patient_coordinate_or_identity_field_exists(self):
        columns = {
            item["name"]
            for item in load_contract("data_contract")["sheets"]["LISTA_ESPERA_AMB"]["columns"]
        }
        forbidden = {
            "patient_id", "rut", "patient_name", "patient_address", "latitude", "longitude"
        }
        self.assertFalse(columns & forbidden)

    def test_professional_map_uses_specialty_without_personal_attribution(self):
        context = {
            "role_id": "professional_clinical",
            "service_id": "especialidades_medicas_adulto",
            "specialty_id": "cardiologia_adulto",
            "simulated_profile_key": "SIM-PROF-C-CARDIOLOGIA-ADULTO-A",
            "professional_lens": "clinical",
        }
        rows = scoped_waitlist_rows(self.dataset, Q2, context)
        self.assertTrue(rows)
        self.assertTrue(all(row["specialty_id"] == "cardiologia_adulto" for row in rows))
        self.assertTrue(any(row["professional_profile_id"] is None for row in rows))

    def test_mixed_lenses_remain_separate_in_complete_context_key(self):
        base = {
            "role_id": "professional_clinical",
            "service_id": "cirugia_infantil",
            "specialty_id": "cirugia_pediatrica",
            "simulated_profile_key": "SIM-PROF-M-PEDIATRICO-A",
        }
        clinical = map_cache_key(self.dataset, Q2, Q1, {**base, "professional_lens": "clinical"})
        surgical = map_cache_key(
            self.dataset,
            Q2,
            Q1,
            {**base, "role_id": "professional_surgical", "professional_lens": "surgical"},
        )
        self.assertNotEqual(clinical, surgical)

    def test_cache_key_includes_complete_filter_context(self):
        base = self.context("urologia")
        values = [
            base,
            {**base, "prestation_type": "consulta_nueva"},
            {**base, "referral_diagnosis_id": "rd_urologia_01"},
            {**base, "selected_center_code": "111101"},
            {**base, "color_mode": "Tendencia"},
        ]
        keys = [map_cache_key(self.dataset, Q2, Q1, value) for value in values]
        self.assertEqual(len(keys), len(set(keys)))

    def test_map_signatures_detect_different_specialties(self):
        signatures = []
        for specialty_id in ("urologia", "neurologia_infantil", "traumatologia"):
            context = self.context(specialty_id)
            rows = origin_bubbles(self.dataset, Q2, Q1, context)
            signatures.append(map_signature(rows, self.dataset, Q2, Q1, context))
        self.assertEqual(len(signatures), len(set(signatures)))

    def test_workbook_filename_matches_contract_13(self):
        contract = load_contract("data_contract")
        self.assertEqual(contract["workbook"]["filename"], "plantilla_carga_hec_1_3.xlsx")
        self.assertTrue((REPO_ROOT / "templates" / contract["workbook"]["filename"]).exists())

    def test_workbook_headers_have_wrapping_height_and_frozen_row(self):
        workbook = REPO_ROOT / "templates" / "plantilla_carga_hec_1_3.xlsx"
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(workbook) as archive:
            for sheet_number in (3, 4, 5, 7):
                root = ElementTree.fromstring(
                    archive.read(f"xl/worksheets/sheet{sheet_number}.xml")
                )
                header = root.find("x:sheetData/x:row[@r='1']", namespace)
                self.assertIsNotNone(header)
                self.assertGreaterEqual(float(header.attrib["ht"]), 42.0)
                pane = root.find("x:sheetViews/x:sheetView/x:pane", namespace)
                self.assertIsNotNone(pane)
                self.assertEqual(pane.attrib["ySplit"], "1")
                self.assertEqual(pane.attrib["state"], "frozen")


if __name__ == "__main__":
    unittest.main()
