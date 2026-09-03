from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_project_config import (
    DEFAULT_CONFIG,
    DEFAULT_SCHEMA,
    validate_config,
)


class ProjectConfigTests(unittest.TestCase):
    def load_template(self) -> dict:
        return yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))

    def validate(self, config: dict) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            return validate_config(path, DEFAULT_SCHEMA)

    def test_published_template_is_valid(self) -> None:
        self.assertEqual(validate_config(DEFAULT_CONFIG, DEFAULT_SCHEMA), [])

    def test_rejects_whole_project_root(self) -> None:
        config = self.load_template()
        config["scope"]["roots"] = ["."]
        self.assertTrue(self.validate(config))

    def test_rejects_parent_traversal(self) -> None:
        config = self.load_template()
        config["scope"]["roots"] = ["../shared"]
        self.assertTrue(self.validate(config))

    def test_rejects_self_analysis(self) -> None:
        config = self.load_template()
        config["scope"]["roots"] = [".evolutive"]
        self.assertTrue(self.validate(config))

    def test_rejects_artifact_not_matching_version(self) -> None:
        config = self.load_template()
        config["constitution"]["version"] = "9.9.9"
        self.assertTrue(self.validate(config))


if __name__ == "__main__":
    unittest.main()
