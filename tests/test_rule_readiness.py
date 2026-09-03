from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

from scripts.validate_rule_readiness import (
    DEFAULT_ASSESSMENTS,
    DEFAULT_RULES,
    DEFAULT_SCHEMA,
    validate_rule_readiness,
)


class RuleReadinessTests(unittest.TestCase):
    def test_canonical_assessments_are_consistent(self) -> None:
        self.assertEqual(validate_rule_readiness(), [])

    def test_requires_assessment_for_every_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            assessments = Path(directory) / "assessments"
            assessments.mkdir()
            for source in DEFAULT_ASSESSMENTS.glob("*.yaml"):
                if source.name != "ARCH-001.yaml":
                    (assessments / source.name).write_text(
                        source.read_text(encoding="utf-8"), encoding="utf-8"
                    )
            failures = validate_rule_readiness(DEFAULT_RULES, assessments, DEFAULT_SCHEMA)
            self.assertTrue(any("avaliação ausente para ARCH-001" in item for item in failures))

    def test_rejects_status_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assessments = root / "assessments"
            assessments.mkdir()
            for source in DEFAULT_ASSESSMENTS.glob("*.yaml"):
                data = yaml.safe_load(source.read_text(encoding="utf-8"))
                if source.name == "ARCH-001.yaml":
                    data["assessed_status"] = "experimental"
                (assessments / source.name).write_text(
                    yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
                )
            failures = validate_rule_readiness(DEFAULT_RULES, assessments, DEFAULT_SCHEMA)
            self.assertTrue(any("assessed_status diverge" in item for item in failures))

    def test_rejects_active_ready_with_unknown_only_checker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assessments = root / "assessments"
            assessments.mkdir()
            for source in DEFAULT_ASSESSMENTS.glob("*.yaml"):
                data = yaml.safe_load(source.read_text(encoding="utf-8"))
                if source.name == "ARCH-001.yaml":
                    data["target_status"] = "active"
                    data["verdict"] = "active_ready"
                    data["criteria"]["enforcement_matches_declared_level"] = True
                    data["enforcement"]["mechanism_available"] = True
                    data["enforcement"]["gaps"] = []
                (assessments / source.name).write_text(
                    yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
                )
            failures = validate_rule_readiness(DEFAULT_RULES, assessments, DEFAULT_SCHEMA)
            self.assertTrue(any("outcome unknown" in item for item in failures))

    def test_rejects_experimental_ready_without_evidence_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assessments = root / "assessments"
            assessments.mkdir()
            for source in DEFAULT_ASSESSMENTS.glob("*.yaml"):
                data = yaml.safe_load(source.read_text(encoding="utf-8"))
                if source.name == "MOD-001.yaml":
                    data["criteria"]["evidence_collection_plan_exists"] = False
                (assessments / source.name).write_text(
                    yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
                )
            failures = validate_rule_readiness(DEFAULT_RULES, assessments, DEFAULT_SCHEMA)
            self.assertTrue(any("critérios mínimos para experimental" in item for item in failures))

    def test_rejects_declared_enforcement_level_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assessments = root / "assessments"
            assessments.mkdir()
            for source in DEFAULT_ASSESSMENTS.glob("*.yaml"):
                data = yaml.safe_load(source.read_text(encoding="utf-8"))
                if source.name == "INT-001.yaml":
                    data["enforcement"]["declared_level"] = "semiautomatic"
                (assessments / source.name).write_text(
                    yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
                )
            failures = validate_rule_readiness(DEFAULT_RULES, assessments, DEFAULT_SCHEMA)
            self.assertTrue(any("declared_level diverge" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
