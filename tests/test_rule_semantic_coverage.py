from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.rule_semantic_coverage import (
    RESULT_SCHEMA,
    assess_rule_semantic_coverage,
    schema_failures,
    validate_semantic_coverage,
)
from scripts.validate_project_config import DEFAULT_CONFIG


class RuleSemanticCoverageTests(unittest.TestCase):
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

    def rules(self, result: dict) -> dict[str, dict]:
        return {item["rule_id"]: item for item in result["rules"]}

    def relation(self, rule: dict, relation_id: str) -> dict:
        return next(item for item in rule["relations"] if item["relation_id"] == relation_id)

    def test_clean_multi_ecosystem_scope_is_partial_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            result = assess_rule_semantic_coverage(config, root)
            rules = self.rules(result)

            for rule_id in ("ARCH-002", "MOD-001"):
                rule = rules[rule_id]
                self.assertEqual(rule["verdict"], "partial")
                self.assertFalse(rule["complete_rule_semantics"])
                self.assertEqual(
                    self.relation(rule, "source_module_dependency")["status"],
                    "covered",
                )
                self.assertIn("taxonomy_not_exhaustive", rule["reasons"])
                self.assertIn("profile_not_exhaustive", rule["reasons"])
                self.assertIn("required_relation_uncovered", rule["reasons"])
                self.assertIn("complete_semantics_not_authorized", rule["reasons"])

            self.assertEqual(
                self.relation(rules["ARCH-002"], "construction_selection")["status"],
                "uncovered",
            )
            self.assertEqual(
                self.relation(rules["MOD-001"], "behavioral_convention_dependency")["status"],
                "uncovered",
            )
            self.assertEqual(validate_semantic_coverage(result, config, root), [])

    def test_insufficient_adapter_coverage_makes_known_relation_partial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/broken.py").write_text("def broken(:\n", encoding="utf-8")
            result = assess_rule_semantic_coverage(config, root)
            rule = self.rules(result)["ARCH-002"]
            self.assertEqual(
                self.relation(rule, "source_module_dependency")["status"],
                "partial",
            )
            self.assertIn("coverage_incomplete", rule["reasons"])
            self.assertIn("required_relation_partial", rule["reasons"])

    def test_known_unsupported_surface_blocks_semantic_completeness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/Main.java").write_text("class Main {}\n", encoding="utf-8")
            result = assess_rule_semantic_coverage(config, root)
            rule = self.rules(result)["ARCH-002"]
            self.assertIn("alignment_incomplete", rule["reasons"])
            self.assertFalse(rule["complete_rule_semantics"])

    def test_unclassified_file_is_explicit_semantic_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/unknown.xyz").write_text("opaque\n", encoding="utf-8")
            result = assess_rule_semantic_coverage(config, root)
            rule = self.rules(result)["MOD-001"]
            self.assertIn("unclassified_files_present", rule["reasons"])
            self.assertFalse(rule["complete_rule_semantics"])

    def test_omitted_detected_observation_is_explicit_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            policy_path = root / ".evolutive/observation-policy.yaml"
            policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
            policy["required_observations"] = [policy["required_observations"][0]]
            policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
            result = assess_rule_semantic_coverage(config, root)
            self.assertIn("alignment_incomplete", self.rules(result)["ARCH-002"]["reasons"])

    def test_schema_rejects_complete_rule_semantics_in_v1(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            result = assess_rule_semantic_coverage(config, root)
            forged = copy.deepcopy(result)
            forged["rules"][0]["complete_rule_semantics"] = True
            failures = schema_failures(RESULT_SCHEMA, forged)
            self.assertTrue(failures)

    def test_existing_assessment_becomes_invalid_after_snapshot_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            result = assess_rule_semantic_coverage(config, root)
            (root / "src/core/api.py").write_text("VALUE = 2\n", encoding="utf-8")
            failures = validate_semantic_coverage(result, config, root)
            self.assertTrue(any("diverge" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
