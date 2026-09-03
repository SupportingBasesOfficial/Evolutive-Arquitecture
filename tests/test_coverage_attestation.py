from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.coverage_attestation import attest_coverage, validate_attestation
from scripts.generate_architecture_evidence import generate_architecture_evidence
from scripts.validate_adapter_contract import MANIFEST_TEMPLATE
from scripts.validate_project_config import DEFAULT_CONFIG

ROOT = Path(__file__).resolve().parents[1]


class CoverageAttestationTests(unittest.TestCase):
    def prepare(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory) / "consumer"
        (root / ".evolutive").mkdir(parents=True)
        (root / "src/core").mkdir(parents=True)
        (root / "src/infra").mkdir(parents=True)
        config = root / ".evolutive/config.yaml"
        config.write_text(DEFAULT_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
        policy = {
            "policy_version": 1,
            "constitution_version": "0.2.0",
            "components": [
                {"id": "core", "roots": ["src/core"], "may_depend_on": [], "public_surface": ["src/core/**"]},
                {"id": "infra", "roots": ["src/infra"], "may_depend_on": ["core"], "public_surface": []},
            ],
        }
        (root / ".evolutive/architecture-policy.yaml").write_text(
            yaml.safe_dump(policy, sort_keys=False), encoding="utf-8"
        )
        (root / "src/core/api.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "src/infra/repo.py").write_text("from core import api\n", encoding="utf-8")
        return root, config

    def attest(self, root: Path, config: Path) -> tuple[dict, dict]:
        evidence = generate_architecture_evidence(config, root, MANIFEST_TEMPLATE)
        attestation = attest_coverage(evidence, config, root, MANIFEST_TEMPLATE)
        return evidence, attestation

    def test_clean_adapter_observation_can_be_attested_sufficient_within_manifest_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            evidence, attestation = self.attest(root, config)
            self.assertEqual(attestation["evaluation"]["verdict"], "sufficient")
            self.assertEqual(attestation["evaluation"]["reasons"], [])
            self.assertEqual(attestation["scope"]["file_extensions"], [".py"])
            self.assertEqual(
                validate_attestation(attestation, evidence, config, root, MANIFEST_TEMPLATE), []
            )

    def test_real_unresolved_reference_prevents_sufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/infra/repo.py").write_text("import core.missing\n", encoding="utf-8")
            _, attestation = self.attest(root, config)
            self.assertEqual(attestation["evaluation"]["verdict"], "insufficient")
            self.assertIn("unresolved_reference", attestation["evaluation"]["reasons"])

    def test_parse_error_and_unanalyzed_file_prevent_sufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/broken.py").write_text("def broken(:\n", encoding="utf-8")
            _, attestation = self.attest(root, config)
            self.assertEqual(attestation["evaluation"]["verdict"], "insufficient")
            self.assertIn("files_not_analyzed", attestation["evaluation"]["reasons"])
            self.assertIn("observation_error", attestation["evaluation"]["reasons"])

    def test_relevant_broker_skip_prevents_sufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/non_utf8.py").write_bytes(b"\xff")
            _, attestation = self.attest(root, config)
            self.assertEqual(attestation["evaluation"]["verdict"], "insufficient")
            self.assertIn("relevant_broker_skip", attestation["evaluation"]["reasons"])

    def test_missing_authorized_root_prevents_sufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            data = yaml.safe_load(config.read_text(encoding="utf-8"))
            data["scope"]["roots"] = ["src", "ghost"]
            config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            _, attestation = self.attest(root, config)
            self.assertEqual(attestation["evaluation"]["verdict"], "insufficient")
            self.assertIn("inventory_gap", attestation["evaluation"]["reasons"])

    def test_stale_or_modified_evidence_is_refused_before_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            evidence = generate_architecture_evidence(config, root, MANIFEST_TEMPLATE)
            changed = copy.deepcopy(evidence)
            changed["graph"]["components"][0]["public_surface"] = []
            with self.assertRaisesRegex(ValueError, "execução fresca"):
                attest_coverage(changed, config, root, MANIFEST_TEMPLATE)

    def test_existing_attestation_is_invalid_after_project_snapshot_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            evidence, attestation = self.attest(root, config)
            (root / "src/core/new.py").write_text("VALUE = 2\n", encoding="utf-8")
            failures = validate_attestation(
                attestation, evidence, config, root, MANIFEST_TEMPLATE
            )
            self.assertTrue(any("execução fresca" in item for item in failures))

    def test_attestation_is_not_part_of_checker_request_contract(self) -> None:
        schema = json.loads((ROOT / "schema/checker-request.schema.json").read_text(encoding="utf-8"))
        self.assertNotIn("coverage_attestation", schema["properties"])


if __name__ == "__main__":
    unittest.main()
