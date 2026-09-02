from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hec_dashboard.app_config import (
    AppConfigError,
    REPO_ROOT as APP_REPO_ROOT,
    get_role_definition,
    load_contract,
    service_choices,
    specialty_choices,
)


class AppConfigTests(unittest.TestCase):
    def test_contract_loading_returns_independent_copies(self):
        first = load_contract("role_matrix")
        second = load_contract("role_matrix")
        self.assertIsNot(first, second)
        first["role_views"].clear()
        self.assertEqual(len(second["role_views"]), 7)

    def test_loading_does_not_depend_on_current_working_directory(self):
        self.assertEqual(load_contract("services")["catalog_version"], "1.1.0")
        self.assertTrue(APP_REPO_ROOT.joinpath("config", "services.json").exists())

    def test_role_lookup_uses_canonical_id(self):
        role = get_role_definition("medical_director")
        self.assertEqual(role["display_name_es"], "Directivo — Director Médico")

    def test_service_filtering_separates_dashboard_types(self):
        clinical = service_choices("clinical")
        surgical = service_choices("surgical")
        self.assertTrue(clinical)
        self.assertTrue(surgical)
        self.assertTrue(all(item["dashboard_type"] == "clinical" for item in clinical))
        self.assertTrue(all(item["dashboard_type"] == "surgical" for item in surgical))
        self.assertFalse({x["unit_id"] for x in clinical} & {x["unit_id"] for x in surgical})

    def test_specialty_hierarchy_is_not_flattened(self):
        specialties = specialty_choices("especialidades_medicas_adulto")
        self.assertTrue(specialties)
        self.assertTrue(
            all(item["parent_unit_id"] == "especialidades_medicas_adulto" for item in specialties)
        )

    def test_invalid_ids_raise_actionable_errors(self):
        with self.assertRaises(AppConfigError):
            get_role_definition("unknown")
        with self.assertRaises(AppConfigError):
            service_choices("mixed")
        with self.assertRaises(AppConfigError):
            specialty_choices("unknown")


if __name__ == "__main__":
    unittest.main()
