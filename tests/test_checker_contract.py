from __future__ import annotations

import json
import unittest

import yaml
from jsonschema import Draft202012Validator

from scripts.validate_checker_contract import (
    MANIFEST_SCHEMA,
    MANIFEST_TEMPLATE,
    REQUEST_SCHEMA,
    RESULT_SCHEMA,
    validate_manifest,
)


class CheckerContractTests(unittest.TestCase):
    def validator(self, path):
        return Draft202012Validator(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def test_manifest_template_is_valid_and_references_known_rules(self) -> None:
        self.assertEqual(validate_manifest(), [])

    def test_manifest_cannot_request_network(self) -> None:
        manifest = yaml.safe_load(MANIFEST_TEMPLATE.read_text(encoding="utf-8"))
        manifest["capabilities"]["network"] = True
        self.assertTrue(list(self.validator(MANIFEST_SCHEMA).iter_errors(manifest)))

    def test_request_cannot_receive_project_root(self) -> None:
        request = {
            "request_version": 1,
            "checker_id": "evolutive.architecture.boundaries",
            "rule_ids": ["ARCH-001"],
            "files": [],
            "project_root": "/workspace/project",
        }
        self.assertTrue(list(self.validator(REQUEST_SCHEMA).iter_errors(request)))

    def test_request_rejects_absolute_file_path(self) -> None:
        request = {
            "request_version": 1,
            "checker_id": "evolutive.architecture.boundaries",
            "rule_ids": ["ARCH-001"],
            "files": [{
                "path": "/etc/passwd",
                "size_bytes": 1,
                "sha256": "0" * 64,
            }],
        }
        self.assertTrue(list(self.validator(REQUEST_SCHEMA).iter_errors(request)))

    def test_result_requires_bounded_metrics(self) -> None:
        result = {
            "result_version": 1,
            "checker_id": "evolutive.architecture.boundaries",
            "checker_version": "0.1.0",
            "outcomes": [],
            "errors": [],
        }
        self.assertTrue(list(self.validator(RESULT_SCHEMA).iter_errors(result)))


if __name__ == "__main__":
    unittest.main()
