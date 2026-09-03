from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.scope_broker import build_inventory
from scripts.validate_project_config import DEFAULT_CONFIG


class ScopeBrokerTests(unittest.TestCase):
    def make_project(self, directory: str) -> tuple[Path, Path]:
        project = Path(directory) / "consumer"
        (project / "src").mkdir(parents=True)
        (project / "tests").mkdir()
        (project / ".evolutive").mkdir()
        (project / "vendor").mkdir()

        (project / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
        (project / "tests" / "test_app.py").write_text("pass", encoding="utf-8")
        (project / ".evolutive" / "private.yaml").write_text("secret", encoding="utf-8")
        (project / "vendor" / "dependency.py").write_text("vendor", encoding="utf-8")
        (project.parent / "outside.txt").write_text("outside", encoding="utf-8")

        config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        config_path = project / ".evolutive" / "config.yaml"
        config_path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return project, config_path

    def test_enumerates_only_authorized_roots_without_reading_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config = self.make_project(directory)
            inventory = build_inventory(config, project)

            self.assertEqual(
                [item["path"] for item in inventory["files"]],
                ["src/app.py", "tests/test_app.py"],
            )
            self.assertFalse(inventory["content_access"]["performed"])
            self.assertEqual(inventory["content_access"]["bytes_read"], 0)
            rendered = str(inventory)
            self.assertNotIn("secret", rendered)
            self.assertNotIn("outside", rendered)
            self.assertNotIn("vendor/dependency.py", rendered)

    def test_skips_symbolic_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config = self.make_project(directory)
            link = project / "src" / "outside-link.txt"
            try:
                os.symlink(project.parent / "outside.txt", link)
            except (OSError, NotImplementedError):
                self.skipTest("links simbólicos indisponíveis neste ambiente")

            inventory = build_inventory(config, project)
            self.assertIn("src/outside-link.txt", inventory["skipped_symlinks"])
            self.assertNotIn(
                "src/outside-link.txt",
                [item["path"] for item in inventory["files"]],
            )

    def test_enforces_file_count_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config = self.make_project(directory)
            with self.assertRaisesRegex(ValueError, "limite"):
                build_inventory(config, project, max_files=1)


if __name__ == "__main__":
    unittest.main()
