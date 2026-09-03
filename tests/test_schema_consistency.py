from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.validate_rule_lifecycle import ALLOWED_TRANSITIONS

ROOT = Path(__file__).resolve().parents[1]


class SchemaConsistencyTests(unittest.TestCase):
    def test_rule_statuses_match_lifecycle_and_report_contracts(self) -> None:
        rule_schema = json.loads((ROOT / "schema" / "rule.schema.json").read_text(encoding="utf-8"))
        report_schema = json.loads((ROOT / "schema" / "conformance-report.schema.json").read_text(encoding="utf-8"))

        canonical = set(rule_schema["properties"]["status"]["enum"])
        lifecycle = set(ALLOWED_TRANSITIONS)
        report = set(
            report_schema["properties"]["rules"]["items"]["properties"]["status"]["enum"]
        )

        self.assertEqual(canonical, lifecycle)
        self.assertEqual(canonical, report)


if __name__ == "__main__":
    unittest.main()
