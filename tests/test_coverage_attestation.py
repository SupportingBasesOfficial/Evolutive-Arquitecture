from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.coverage_attestation import attest_coverage, validate_attestation
from scripts.generate_architecture_evidence import generate_architecture_evidence
from scripts.validate_adapter_contract import MANIFEST_TEMPLATE
from scripts.validate_project_config import DEFAULT_CONFIG


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

    def test_clean_adapter_observation_can_be_attested_sufficient_within_manifest_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            evidence = generate_architecture_evidence(config, root, MANIFEST_TEMPLATE)
            attestation = attest_coverage(evidence, MANIFEST_TEMPLATE)
            self.assertEqual(attestation["evaluation"]["verdict"], "sufficient")
            self.assertEqual(attestation["evaluation"]["reasons"], [])
            self.assertEqual(attestation["scope"]["file_extensions"], [".py"])
            self.assertEqual(validate_attestation(attestation, evidence, MANIFEST_TEMPLATE), [])

    def test_unresolved_reference_prevents_sufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            evidence = generate_architecture_evidence(config, root, MANIFEST_TEMPLATE)
            evidence["observation"]["coverage"]["unresolved_references"] = 1
            attestation = attest_coverage(evidence, MANIFEST_TEMPLATE)
            self.assertEqual(attestation["evaluation"]["verdict"], "insufficient")
            self.assertIn("unresolved_reference", attestation["evaluation"]["reasons"])

    def test_parse_error_and_unanalyzed_file_prevent_sufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/broken.py").write_text("def broken(:\n", encoding="utf-8")
            evidence = generate_architecture_evidence(config, root, MANIFEST_TEMPLATE)
            attestation = attest_coverage(evidence, MANIFEST_TEMPLATE)
            self.assertEqual(attestation["evaluation"]["verdict"], "insufficient")
            self.assertIn("files_not_analyzed", attestation["evaluation"]["reasons"])
            self.assertIn("observation_error", attestation["evaluation"]["reasons"])

    def test_relevant_broker_skip_prevents_sufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/non_utf8.py").write_bytes(b"\xff")
            evidence = generate_architecture_evidence(config, root, MANIFEST_TEMPLATE)
            attestation = attest_coverage(evidence, MANIFEST_TEMPLATE)
            self.assertEqual(attestation["evaluation"]["verdict"], "insufficient")
            self.assertIn("relevant_broker_skip", attestation["evaluation"]["reasons"])

    def test_inventory_gap_prevents_sufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            evidence = generate_architecture_evidence(config, root, MANIFEST_TEMPLATE)
            evidence["observation"]["broker_audit"]["skipped_symlinks"] = ["src/core/link.py"]
            attestation = attest_coverage(evidence, MANIFEST_TEMPLATE)
            self.assertEqual(attestation["evaluation"]["verdict"], "insufficient")
            self.assertIn("inventory_gap", attestation["evaluation"]["reasons"])

    def test_attestation_is_bound_to_exact_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            evidence = generate_architecture_evidence(config, root, MANIFEST_TEMPLATE)
            attestation = attest_coverage(evidence, MANIFEST_TEMPLATE)
            changed = copy.deepcopy(evidence)
            changed["graph"]["components"][0]["public_surface"] = []
            failures = validate_attestation(attestation, changed, MANIFEST_TEMPLATE)
            self.assertTrue(any("diverge" in item for item in failures))

    def test_supported_extension_cannot_be_hidden_as_extension_not_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            evidence = generate_architecture_evidence(config, root, MANIFEST_TEMPLATE)
            audit = evidence["observation"]["broker_audit"]
            audit["files_delivered"] -= 1
            audit["skipped"].append({"path": "src/core/api.py", "reason": "extension_not_allowed"})
            with self.assertRaisesRegex(ValueError, "arquivo suportado"):
                attest_coverage(evidence, MANIFEST_TEMPLATE)


if __name__ == "__main__":
    unittest.main()
