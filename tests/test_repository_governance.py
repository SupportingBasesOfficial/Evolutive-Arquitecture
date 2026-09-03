from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

from scripts.validate_repository_governance import (
    DEFAULT_POLICY,
    DEFAULT_SCHEMA,
    DEFAULT_WORKFLOW,
    validate_repository_governance,
)


class RepositoryGovernanceTests(unittest.TestCase):
    def test_canonical_contract_matches_workflow(self) -> None:
        self.assertEqual(validate_repository_governance(), [])

    def test_detects_required_check_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = yaml.safe_load(DEFAULT_POLICY.read_text(encoding="utf-8"))
            policy["main_branch"]["required_status_checks"] = ["validate (ubuntu-latest)"]
            policy_path = root / "repository.yaml"
            policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

            failures = validate_repository_governance(
                policy_path,
                DEFAULT_SCHEMA,
                DEFAULT_WORKFLOW,
            )
            self.assertTrue(any("required_status_checks divergem" in item for item in failures))

    def test_schema_rejects_non_squash_merge_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = yaml.safe_load(DEFAULT_POLICY.read_text(encoding="utf-8"))
            policy["merge_policy"]["allowed_methods"] = ["merge", "squash"]
            policy_path = root / "repository.yaml"
            policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

            failures = validate_repository_governance(
                policy_path,
                DEFAULT_SCHEMA,
                DEFAULT_WORKFLOW,
            )
            self.assertTrue(any("allowed_methods" in item for item in failures))

    def test_schema_forbids_bypass_actors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = yaml.safe_load(DEFAULT_POLICY.read_text(encoding="utf-8"))
            policy["main_branch"]["bypass_actors"] = ["admin"]
            policy_path = root / "repository.yaml"
            policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

            failures = validate_repository_governance(
                policy_path,
                DEFAULT_SCHEMA,
                DEFAULT_WORKFLOW,
            )
            self.assertTrue(any("bypass_actors" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
