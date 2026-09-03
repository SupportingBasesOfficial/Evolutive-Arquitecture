from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class TemplateSerializationTests(unittest.TestCase):
    def test_rule_decision_date_remains_a_string(self) -> None:
        template = yaml.safe_load(
            (ROOT / "templates" / "rule-decision.yaml").read_text(encoding="utf-8")
        )
        self.assertIsInstance(template["decision"]["decided_at"], str)


if __name__ == "__main__":
    unittest.main()
