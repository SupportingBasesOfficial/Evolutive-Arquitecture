from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_rules import DEFAULT_SCHEMA, validate_catalog


class CatalogBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.rules = self.root / "rules"
        (self.rules / "universal").mkdir(parents=True)

        self.valid_rule = {
            "id": "TEST-001",
            "title": "Regra válida para teste",
            "layer": "universal",
            "normativity": "MUST",
            "statement": "O componente deve cumprir uma condição verificável.",
            "rationale": "A condição protege uma qualidade arquitetural identificável.",
            "scope": {"applies_to": ["Fixture"], "excludes": []},
            "compliance": {
                "pass_conditions": ["A condição está presente"],
                "fail_conditions": ["A condição está ausente"],
            },
            "enforcement": {"level": "automatic", "mechanism": "Teste automatizado"},
            "examples": {
                "compliant": ["Fixture válida"],
                "noncompliant": ["Fixture inválida"],
            },
            "exceptions": {"allowed": False, "conditions": []},
            "status": "proposed",
            "introduced_in": "0.1.0",
            "deprecated_in": None,
            "superseded_by": None,
            "references": [],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_rule(self, name: str, rule: dict) -> None:
        path = self.rules / "universal" / name
        path.write_text(
            yaml.safe_dump(rule, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def test_accepts_valid_catalog(self) -> None:
        self.write_rule("TEST-001.yaml", self.valid_rule)
        self.assertEqual(validate_catalog(DEFAULT_SCHEMA, self.rules), [])

    def test_rejects_invalid_rule(self) -> None:
        invalid = dict(self.valid_rule)
        invalid.pop("statement")
        self.write_rule("TEST-001.yaml", invalid)
        self.assertTrue(validate_catalog(DEFAULT_SCHEMA, self.rules))

    def test_does_not_scan_outside_explicit_rules_directory(self) -> None:
        self.write_rule("TEST-001.yaml", self.valid_rule)
        unrelated = self.root / "project-source"
        unrelated.mkdir()
        (unrelated / "invalid.yaml").write_text("not: a rule", encoding="utf-8")
        self.assertEqual(validate_catalog(DEFAULT_SCHEMA, self.rules), [])


if __name__ == "__main__":
    unittest.main()
