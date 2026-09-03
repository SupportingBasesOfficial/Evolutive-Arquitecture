from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.run_checker import execute_checker
from scripts.validate_checker_contract import MANIFEST_TEMPLATE


class CheckerRunnerTests(unittest.TestCase):
    def request(self) -> dict:
        payload = b"pass"
        return {
            "request_version": 1,
            "checker_id": "evolutive.architecture.boundaries",
            "rule_ids": ["ARCH-001", "ARCH-002"],
            "files": [{
                "path": "src/app.py",
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "text": payload.decode("utf-8"),
            }],
        }

    def write_manifest(self, directory: str, mutate=None) -> Path:
        manifest = yaml.safe_load(MANIFEST_TEMPLATE.read_text(encoding="utf-8"))
        if mutate:
            mutate(manifest)
        path = Path(directory) / "manifest.yaml"
        path.write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return path

    def test_registered_checker_returns_conservative_unknown(self) -> None:
        result = execute_checker(MANIFEST_TEMPLATE, self.request())
        self.assertEqual(
            [item["status"] for item in result["outcomes"]],
            ["unknown", "unknown"],
        )
        self.assertEqual(result["metrics"]["files_received"], 1)
        self.assertEqual(result["metrics"]["bytes_received"], 4)

    def test_rejects_unregistered_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_manifest(
                directory,
                lambda item: item["runtime"].update(
                    entrypoint="evolutive.checkers.other:check"
                ),
            )
            with self.assertRaisesRegex(ValueError, "registro interno"):
                execute_checker(manifest, self.request())

    def test_rejects_tampered_checker_implementation_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_manifest(
                directory,
                lambda item: item["runtime"].update(
                    implementation_sha256="0" * 64
                ),
            )
            with self.assertRaisesRegex(ValueError, "checksum da implementação"):
                execute_checker(manifest, self.request())

    def test_rejects_content_without_capability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_manifest(
                directory,
                lambda item: item["capabilities"].update(content_access="none"),
            )
            with self.assertRaisesRegex(ValueError, "não autorizado"):
                execute_checker(manifest, self.request())

    def test_rejects_rule_outside_manifest_grant(self) -> None:
        request = self.request()
        request["rule_ids"].append("OTHER-001")
        with self.assertRaises(ValueError):
            execute_checker(MANIFEST_TEMPLATE, request)

    def test_rejects_project_root_field(self) -> None:
        request = self.request()
        request["project_root"] = "/workspace/project"
        with self.assertRaisesRegex(ValueError, "requisição inválida"):
            execute_checker(MANIFEST_TEMPLATE, request)

    def test_rejects_content_with_tampered_hash(self) -> None:
        request = self.request()
        request["files"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "checksum inconsistente"):
            execute_checker(MANIFEST_TEMPLATE, request)


if __name__ == "__main__":
    unittest.main()
