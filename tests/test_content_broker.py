from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from scripts.content_broker import build_checker_request
from scripts.validate_checker_contract import (
    MANIFEST_SCHEMA,
    MANIFEST_TEMPLATE,
    REQUEST_SCHEMA,
)
from scripts.validate_project_config import DEFAULT_CONFIG


class ContentBrokerTests(unittest.TestCase):
    def prepare(self, directory: str) -> tuple[Path, Path, Path]:
        project = Path(directory) / "consumer"
        (project / "src").mkdir(parents=True)
        (project / "tests").mkdir()
        (project / ".evolutive").mkdir()
        (project / "src" / "app.py").write_text("answer = 42\n", encoding="utf-8")
        (project / "src" / "large.py").write_text("x" * 32, encoding="utf-8")
        (project / "src" / "binary.py").write_bytes(b"\xff\xfe")
        (project.parent / "outside.py").write_text("secret", encoding="utf-8")

        config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        config_path = project / ".evolutive" / "config.yaml"
        config_path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        manifest = yaml.safe_load(MANIFEST_TEMPLATE.read_text(encoding="utf-8"))
        manifest["capabilities"]["file_extensions"] = [".py"]
        manifest["capabilities"]["max_file_bytes"] = 16
        manifest_path = Path(directory) / "manifest.yaml"
        manifest_path.write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return project, config_path, manifest_path

    def test_builds_schema_valid_request_without_disclosing_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config, manifest = self.prepare(directory)
            request, audit = build_checker_request(config, project, manifest)

            schema = json.loads(REQUEST_SCHEMA.read_text(encoding="utf-8"))
            self.assertEqual(
                list(Draft202012Validator(schema).iter_errors(request)),
                [],
            )
            self.assertEqual([item["path"] for item in request["files"]], ["src/app.py"])
            self.assertEqual(request["files"][0]["text"], "answer = 42\n")
            self.assertFalse(audit["project_root_disclosed"])
            self.assertNotIn(str(project), json.dumps(request))
            reasons = {item["path"]: item["reason"] for item in audit["skipped"]}
            self.assertIn("limite", reasons["src/large.py"])
            self.assertEqual(reasons["src/binary.py"], "not_utf8")

    def test_omits_text_when_capability_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config, manifest_path = self.prepare(directory)
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["capabilities"]["content_access"] = "none"
            manifest_path.write_text(
                yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            request, _ = build_checker_request(config, project, manifest_path)
            self.assertNotIn("text", request["files"][0])

    def test_never_delivers_symbolic_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config, manifest = self.prepare(directory)
            link = project / "src" / "outside.py"
            try:
                os.symlink(project.parent / "outside.py", link)
            except (OSError, NotImplementedError):
                self.skipTest("links simbólicos indisponíveis neste ambiente")

            request, _ = build_checker_request(config, project, manifest)
            self.assertNotIn(
                "src/outside.py",
                [item["path"] for item in request["files"]],
            )


if __name__ == "__main__":
    unittest.main()
