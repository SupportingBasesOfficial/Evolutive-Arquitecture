from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import scripts.result_aggregation as aggregation_module
from scripts.result_aggregation import aggregate_results, validate_aggregated_result
from scripts.validate_project_config import DEFAULT_CONFIG


class ResultAggregationTests(unittest.TestCase):
    def prepare(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory) / "consumer"
        (root / ".evolutive").mkdir(parents=True)
        (root / "src/core").mkdir(parents=True)
        (root / "src/infra").mkdir(parents=True)

        config = root / ".evolutive/config.yaml"
        data = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        data["scope"]["roots"] = ["src"]
        config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

        architecture_policy = {
            "policy_version": 1,
            "constitution_version": "0.2.0",
            "components": [
                {
                    "id": "core",
                    "roots": ["src/core"],
                    "may_depend_on": [],
                    "public_surface": ["src/core/**"],
                },
                {
                    "id": "infra",
                    "roots": ["src/infra"],
                    "may_depend_on": ["core"],
                    "public_surface": ["src/infra/public/**"],
                },
            ],
        }
        (root / ".evolutive/architecture-policy.yaml").write_text(
            yaml.safe_dump(architecture_policy, sort_keys=False), encoding="utf-8"
        )

        observation_policy = {
            "policy_version": 1,
            "constitution_version": "0.2.0",
            "required_observations": [
                {"adapter_id": "evolutive.python.imports", "adapter_version": "0.1.0"},
                {"adapter_id": "evolutive.ecmascript.imports", "adapter_version": "0.1.0"},
            ],
        }
        (root / ".evolutive/observation-policy.yaml").write_text(
            yaml.safe_dump(observation_policy, sort_keys=False), encoding="utf-8"
        )

        (root / "src/core/api.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "src/infra/repo.py").write_text("from core import api\n", encoding="utf-8")
        (root / "src/core/api.ts").write_text("export const value = 1;\n", encoding="utf-8")
        (root / "src/infra/repo.ts").write_text(
            'import { value } from "../core/api";\nexport { value };\n', encoding="utf-8"
        )
        return root, config

    def outcomes(self, result: dict) -> dict[str, dict]:
        return {item["rule_id"]: item for item in result["outcomes"]}

    def test_clean_scope_verifies_positive_evidence_without_normative_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            result = aggregate_results(config, root)
            outcomes = self.outcomes(result)

            for rule_id in ("ARCH-002", "MOD-001"):
                outcome = outcomes[rule_id]
                self.assertEqual(outcome["status"], "unknown")
                self.assertEqual(outcome["positive_evidence"], "verified")
                self.assertEqual(outcome["basis"], "positive_evidence_verified")
                self.assertEqual(outcome["claim_scope"], "observed_dependency_graph")
                self.assertFalse(outcome["complete_rule_semantics"])
                self.assertIn("complete_rule_semantics_not_proven", outcome["reasons"])

            for rule_id in ("ARCH-001", "INT-001"):
                outcome = outcomes[rule_id]
                self.assertEqual(outcome["status"], "unknown")
                self.assertEqual(outcome["positive_evidence"], "not_authorized")
                self.assertEqual(outcome["basis"], "no_positive_profile")
                self.assertEqual(outcome["claim_scope"], "none")

            self.assertTrue(
                all(
                    row["checker_status"] == "unknown"
                    for rule_id in ("ARCH-002", "MOD-001")
                    for row in outcomes[rule_id]["checker_observations"]
                )
            )
            self.assertTrue(all(item["status"] in {"fail", "unknown"} for item in result["outcomes"]))
            self.assertEqual(validate_aggregated_result(result, config, root), [])

    def test_checker_fail_has_precedence_over_positive_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/bad.ts").write_text(
                'import { value } from "../infra/repo";\nexport { value };\n', encoding="utf-8"
            )
            result = aggregate_results(config, root)
            outcome = self.outcomes(result)["ARCH-002"]
            self.assertEqual(outcome["status"], "fail")
            self.assertEqual(outcome["positive_evidence"], "insufficient")
            self.assertEqual(outcome["basis"], "checker_fail")

    def test_omitted_detected_observation_keeps_positive_evidence_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            path = root / ".evolutive/observation-policy.yaml"
            policy = yaml.safe_load(path.read_text(encoding="utf-8"))
            policy["required_observations"] = [policy["required_observations"][0]]
            path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
            result = aggregate_results(config, root)
            outcome = self.outcomes(result)["ARCH-002"]
            self.assertEqual(outcome["status"], "unknown")
            self.assertEqual(outcome["positive_evidence"], "insufficient")
            self.assertIn("alignment_incomplete", outcome["reasons"])

    def test_known_unsupported_surface_keeps_positive_evidence_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/Main.java").write_text("class Main {}\n", encoding="utf-8")
            result = aggregate_results(config, root)
            outcome = self.outcomes(result)["ARCH-002"]
            self.assertEqual(outcome["status"], "unknown")
            self.assertEqual(outcome["positive_evidence"], "insufficient")
            self.assertIn("alignment_incomplete", outcome["reasons"])

    def test_unclassified_file_keeps_positive_evidence_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/unknown.xyz").write_text("opaque\n", encoding="utf-8")
            result = aggregate_results(config, root)
            outcome = self.outcomes(result)["ARCH-002"]
            self.assertEqual(outcome["status"], "unknown")
            self.assertEqual(outcome["positive_evidence"], "insufficient")
            self.assertIn("unclassified_files_present", outcome["reasons"])

    def test_fresh_attestation_must_match_exact_composed_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            original = aggregation_module.attest_coverage

            def drifted_attestation(*args, **kwargs):
                attestation = copy.deepcopy(original(*args, **kwargs))
                attestation["subject"]["delivered_content_sha256"] = "f" * 64
                return attestation

            with patch.object(aggregation_module, "attest_coverage", side_effect=drifted_attestation):
                with self.assertRaisesRegex(ValueError, "attestation fresca diverge da attestation composta"):
                    aggregate_results(config, root)

    def test_existing_result_becomes_invalid_after_snapshot_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            result = aggregate_results(config, root)
            (root / "src/core/api.py").write_text("VALUE = 2\n", encoding="utf-8")
            failures = validate_aggregated_result(result, config, root)
            self.assertTrue(any("diverge" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
