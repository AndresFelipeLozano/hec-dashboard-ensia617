import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_contracts import (  # noqa: E402
    ContractValidationError,
    check_limit,
    validate_contracts,
    validate_references,
    validate_unique_ids,
)


class ContractTests(unittest.TestCase):
    def test_real_project_contracts_validate_completely(self):
        counts = validate_contracts(REPO_ROOT)
        self.assertEqual(counts["contract_files"], 5)
        self.assertEqual(counts["indicators"], 31)
        self.assertEqual(counts["roles"], 7)
        self.assertEqual(counts["units"], 30)
        self.assertEqual(counts["specialties"], 26)
        self.assertEqual(counts["simulated_professional_profiles"], 27)
        self.assertEqual(counts["maps"], 6)
        self.assertEqual(counts["finding_rules"], 19)
        self.assertEqual(counts["view_limits"], 7)
        self.assertEqual(counts["safety_controls"], 30)

    def test_unique_ids_accepts_unique_values(self):
        ids, errors = validate_unique_ids(
            [{"role_id": "director"}, {"role_id": "medical_director"}],
            "role_id",
            "test.roles",
        )
        self.assertEqual(ids, {"director", "medical_director"})
        self.assertEqual(errors, [])

    def test_unique_ids_reports_duplicates_actionably(self):
        _, errors = validate_unique_ids(
            [{"indicator_id": "wait"}, {"indicator_id": "wait"}],
            "indicator_id",
            "test.indicators",
        )
        self.assertEqual(
            errors,
            ["test.indicators: duplicate indicator_id 'wait'"],
        )

    def test_reference_validation_reports_unknown_id(self):
        count, errors = validate_references(
            ["director", "unknown"], {"director"}, "test.role_reference"
        )
        self.assertEqual(count, 2)
        self.assertEqual(
            errors,
            ["test.role_reference: unknown reference 'unknown'"],
        )

    def test_limit_invariant(self):
        scenarios = [
            (6, 6, False),
            (5, 5, False),
            (7, 6, True),
            (-1, 6, True),
        ]
        for value, maximum, has_error in scenarios:
            with self.subTest(value=value, maximum=maximum):
                errors = check_limit(value, maximum, "test.limit")
                self.assertIs(bool(errors), has_error)

    def test_mixed_profile_contract_rejects_two_specialties(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config"
            config.mkdir()
            for name in (
                "services.json",
                "indicators.json",
                "role_matrix.json",
                "ui_contract.json",
                "professional_profiles.json",
            ):
                shutil.copy2(REPO_ROOT / "config" / name, config / name)
            path = config / "professional_profiles.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            mixed = next(
                profile
                for profile in contract["profiles"]
                if profile["profile_type"] == "mixed"
            )
            mixed["lens_contexts"]["clinical"]["specialty_id"] = "pediatria"
            path.write_text(
                json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ContractValidationError, "preserve mixed specialty_id"
            ):
                validate_contracts(root)


if __name__ == "__main__":
    unittest.main()
