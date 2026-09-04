from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.coverage_composition import compose_coverage, validate_composition
from scripts.observation_policy import validate_observation_policy
from scripts.validate_project_config import DEFAULT_CONFIG


class CoverageCompositionTests(unittest.TestCase):
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
                    "public_surface": [],
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
            'import { value } from "../core/api";\nexport { value };\n',
            encoding="utf-8",
        )
        return root, config

    def test_python_and_ecmascript_can_compose_complete_on_same_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            composition = compose_coverage(config, root)
            self.assertEqual(composition["scope"]["basis"], "declared_observation_policy")
            self.assertEqual(composition["evaluation"]["verdict"], "complete")
            self.assertEqual(composition["evaluation"]["required_count"], 2)
            self.assertEqual(composition["evaluation"]["sufficient_count"], 2)
            self.assertEqual(
                {row["coverage_verdict"] for row in composition["evaluation"]["observations"]},
                {"sufficient"},
            )
            self.assertEqual(validate_composition(composition, config, root), [])

    def test_one_insufficient_required_observation_makes_composition_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/infra/repo.ts").write_text(
                'import { value } from "@app/core";\nexport { value };\n',
                encoding="utf-8",
            )
            composition = compose_coverage(config, root)
            self.assertEqual(composition["evaluation"]["verdict"], "incomplete")
            self.assertEqual(composition["evaluation"]["sufficient_count"], 1)
            self.assertEqual(
                composition["evaluation"]["reasons"],
                ["required_observation_insufficient"],
            )

    def test_duplicate_required_adapter_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            path = root / ".evolutive/observation-policy.yaml"
            policy = yaml.safe_load(path.read_text(encoding="utf-8"))
            policy["required_observations"].append(copy.deepcopy(policy["required_observations"][0]))
            path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
            _, failures = validate_observation_policy(config, root)
            self.assertTrue(any("duplicado" in item for item in failures))

    def test_unknown_required_adapter_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            path = root / ".evolutive/observation-policy.yaml"
            policy = yaml.safe_load(path.read_text(encoding="utf-8"))
            policy["required_observations"] = [
                {"adapter_id": "evolutive.unknown.imports", "adapter_version": "0.1.0"}
            ]
            path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
            _, failures = validate_observation_policy(config, root)
            self.assertTrue(any("não existe" in item for item in failures))

    def test_required_adapter_version_must_match_canonical_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            path = root / ".evolutive/observation-policy.yaml"
            policy = yaml.safe_load(path.read_text(encoding="utf-8"))
            policy["required_observations"][0]["adapter_version"] = "9.9.9"
            path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
            _, failures = validate_observation_policy(config, root)
            self.assertTrue(any("diverge" in item for item in failures))

    def test_existing_composition_becomes_invalid_when_policy_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            composition = compose_coverage(config, root)
            path = root / ".evolutive/observation-policy.yaml"
            policy = yaml.safe_load(path.read_text(encoding="utf-8"))
            policy["required_observations"] = [policy["required_observations"][0]]
            path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
            failures = validate_composition(composition, config, root)
            self.assertTrue(any("diverge" in item for item in failures))

    def test_composer_output_has_no_rule_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            composition = compose_coverage(config, root)
            self.assertNotIn("rule_outcome", composition)
            self.assertNotIn("pass", composition["evaluation"])


if __name__ == "__main__":
    unittest.main()
