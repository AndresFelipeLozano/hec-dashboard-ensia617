from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hec_dashboard.app_config import REPO_ROOT
from hec_dashboard.app_state import (
    Keys,
    activate_candidate,
    initialize_session,
    reset_role,
    restore_bundled_dataset,
    set_role_context,
    validate_candidate_bytes,
)


class AppStateTests(unittest.TestCase):
    def setUp(self):
        self.state = {}
        initialize_session(self.state)

    def test_initialization_activates_bundled_validated_dataset(self):
        self.assertTrue(self.state[Keys.INITIALIZED])
        self.assertEqual(
            self.state[Keys.ACTIVE_DATASET_METADATA]["dataset_id"], "hec-sim-day4r-v2"
        )
        self.assertEqual(self.state[Keys.ACTIVE_VALIDATION_SUMMARY]["accepted_rows"], 8960)
        self.assertEqual(self.state[Keys.ACTIVE_VALIDATION_SUMMARY]["rejected_rows"], 0)

    def test_initialization_is_idempotent(self):
        active = self.state[Keys.ACTIVE_DATASET]
        initialize_session(self.state)
        self.assertIs(self.state[Keys.ACTIVE_DATASET], active)

    def test_valid_candidate_remains_separate_until_activation(self):
        active = self.state[Keys.ACTIVE_DATASET]
        data = (REPO_ROOT / "templates" / "plantilla_carga_hec_v1.xlsx").read_bytes()
        report = validate_candidate_bytes(self.state, "candidate.xlsx", data)
        self.assertTrue(report.activatable)
        self.assertIs(self.state[Keys.ACTIVE_DATASET], active)
        self.assertIsNotNone(self.state[Keys.CANDIDATE_DATASET])
        activated = activate_candidate(self.state)
        self.assertIsNot(self.state[Keys.ACTIVE_DATASET], self.state[Keys.CANDIDATE_DATASET])
        self.assertEqual(activated.metadata["dataset_id"], "hec-sim-day4r-v2")

    def test_failed_candidate_preserves_active_dataset(self):
        active = self.state[Keys.ACTIVE_DATASET]
        with self.assertRaises(ValueError):
            validate_candidate_bytes(self.state, "invalid.xlsx", b"not-an-xlsx")
        self.assertIs(self.state[Keys.ACTIVE_DATASET], active)
        self.assertIsNone(self.state[Keys.CANDIDATE_DATASET])

    def test_reset_role_preserves_active_dataset(self):
        active = self.state[Keys.ACTIVE_DATASET]
        set_role_context(self.state, {"role_id": "director"})
        reset_role(self.state)
        self.assertIsNone(self.state[Keys.ROLE_CONTEXT])
        self.assertIs(self.state[Keys.ACTIVE_DATASET], active)

    def test_restore_bundled_dataset_revalidates_default(self):
        self.state[Keys.ACTIVE_SOURCE_MODE] = "uploaded"
        restored = restore_bundled_dataset(self.state)
        self.assertEqual(restored.metadata["dataset_id"], "hec-sim-day4r-v2")
        self.assertEqual(
            self.state[Keys.ACTIVE_SOURCE_MODE],
            "bundled_validated_simulated_session_only",
        )

    def test_sessions_do_not_share_active_mutable_objects(self):
        other = {}
        initialize_session(other)
        self.assertIsNot(self.state[Keys.ACTIVE_DATASET], other[Keys.ACTIVE_DATASET])
        self.assertIsNot(
            self.state[Keys.ACTIVE_DATASET].tables,
            other[Keys.ACTIVE_DATASET].tables,
        )


if __name__ == "__main__":
    unittest.main()
