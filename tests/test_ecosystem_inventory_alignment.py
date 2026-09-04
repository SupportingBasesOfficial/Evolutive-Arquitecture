from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.ecosystem_inventory import discover_ecosystems
from scripts.observation_alignment import align_observation_policy, validate_alignment
from scripts.validate_project_config import DEFAULT_CONFIG


class EcosystemInventoryAlignmentTests(unittest.TestCase):
    def prepare(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory) / "consumer"
        (root / ".evolutive").mkdir(parents=True)
        (root / "src").mkdir(parents=True)

        config = root / ".evolutive/config.yaml"
        data = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        data["scope"]["roots"] = ["src"]
        config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

        policy = {
            "policy_version": 1,
            "constitution_version": "0.2.0",
            "required_observations": [
                {"adapter_id": "evolutive.python.imports", "adapter_version": "0.1.0"},
                {"adapter_id": "evolutive.ecmascript.imports", "adapter_version": "0.1.0"},
            ],
        }
        (root / ".evolutive/observation-policy.yaml").write_text(
            yaml.safe_dump(policy, sort_keys=False), encoding="utf-8"
        )
        (root / "src/app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "src/app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        return root, config

    def test_known_supported_surfaces_align_with_declared_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            inventory = discover_ecosystems(config, root)
            self.assertEqual(
                {row["surface_id"] for row in inventory["detected_surfaces"]},
                {"python-source", "ecmascript-source"},
            )
            alignment = align_observation_policy(config, root)
            self.assertEqual(alignment["evaluation"]["verdict"], "aligned")
            self.assertEqual(alignment["evaluation"]["missing_observations"], [])
            self.assertEqual(alignment["evaluation"]["unsupported_surfaces"], [])

    def test_omitted_detected_adapter_makes_alignment_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            path = root / ".evolutive/observation-policy.yaml"
            policy = yaml.safe_load(path.read_text(encoding="utf-8"))
            policy["required_observations"] = [policy["required_observations"][0]]
            path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
            alignment = align_observation_policy(config, root)
            self.assertEqual(alignment["evaluation"]["verdict"], "incomplete")
            self.assertEqual(alignment["evaluation"]["reasons"], ["missing_required_observation"])
            self.assertEqual(
                alignment["evaluation"]["missing_observations"],
                [{"adapter_id": "evolutive.ecmascript.imports", "adapter_version": "0.1.0"}],
            )

    def test_known_unsupported_language_surface_blocks_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/Main.java").write_text("class Main {}\n", encoding="utf-8")
            alignment = align_observation_policy(config, root)
            self.assertEqual(alignment["evaluation"]["verdict"], "incomplete")
            self.assertIn("java-source", alignment["evaluation"]["unsupported_surfaces"])
            self.assertIn("unsupported_detected_surface", alignment["evaluation"]["reasons"])

    def test_known_unsupported_tsx_surface_blocks_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/view.tsx").write_text("export const View = () => null;\n", encoding="utf-8")
            alignment = align_observation_policy(config, root)
            self.assertIn("ecmascript-jsx-source", alignment["evaluation"]["unsupported_surfaces"])

    def test_unclassified_files_are_reported_but_not_silently_classified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/README.md").write_text("docs\n", encoding="utf-8")
            alignment = align_observation_policy(config, root)
            self.assertEqual(alignment["evaluation"]["verdict"], "aligned")
            self.assertEqual(alignment["evaluation"]["unclassified_files"]["count"], 1)
            self.assertEqual(alignment["evaluation"]["unclassified_files"]["extensions"], [".md"])
            self.assertTrue(alignment["scope"]["catalog_scope_only"])

    def test_existing_alignment_is_stale_after_new_known_surface_appears(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            alignment = align_observation_policy(config, root)
            (root / "src/main.go").write_text("package main\n", encoding="utf-8")
            failures = validate_alignment(alignment, config, root)
            self.assertTrue(any("diverge" in item for item in failures))

    def test_alignment_has_no_rule_outcome_or_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            alignment = align_observation_policy(config, root)
            self.assertNotIn("rule_outcome", alignment)
            self.assertNotIn("pass", alignment["evaluation"])


if __name__ == "__main__":
    unittest.main()
