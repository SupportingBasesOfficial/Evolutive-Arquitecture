from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

from scripts.validate_project_exceptions import (
    DEFAULT_SCHEMA,
    resolve_exception_directory,
    validate_exception_records,
)


class ProjectExceptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.exceptions = self.root / ".evolutive" / "exceptions"
        self.exceptions.mkdir(parents=True)
        self.rules = [
            {
                "id": "MOD-001",
                "status": "active",
                "exceptions": {"allowed": True, "conditions": ["Temporária"]},
            },
            {
                "id": "ARCH-001",
                "status": "active",
                "exceptions": {"allowed": False, "conditions": []},
            },
        ]
        self.record = {
            "exception_id": "EXC-0001",
            "rule_id": "MOD-001",
            "constitution_version": "0.2.0",
            "context": "Migração temporária de uma fronteira legada.",
            "justification": "A remoção imediata quebraria uma migração controlada em andamento.",
            "responsible": "Architecture Team",
            "risks_accepted": ["Acoplamento temporário entre módulos"],
            "compensating_controls": ["Teste de contrato e revisão semanal"],
            "condition_evidence": [
                {
                    "condition": "Temporária",
                    "evidence": "Ticket MIG-42 possui prazo explícito de remoção",
                }
            ],
            "scope": {"paths": ["src/legacy"]},
            "validity": {"expires_on": "2026-12-31", "review_condition": None},
            "decision": {
                "outcome": "approved",
                "authority": "Architecture Board",
                "decided_at": "2026-09-03",
            },
            "references": [],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, record: dict, name: str | None = None) -> None:
        path = self.exceptions / (name or f"{record['exception_id']}.yaml")
        path.write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def validate(self) -> list[str]:
        return validate_exception_records(
            self.exceptions,
            self.rules,
            "0.2.0",
            ["src", "tests"],
            DEFAULT_SCHEMA,
        )

    def test_accepts_limited_approved_exception(self) -> None:
        self.write(self.record)
        self.assertEqual(self.validate(), [])

    def test_rejects_exception_when_rule_forbids_it(self) -> None:
        record = deepcopy(self.record)
        record["rule_id"] = "ARCH-001"
        self.write(record)
        self.assertTrue(any("não permite exceções" in item for item in self.validate()))

    def test_rejects_approved_exception_for_non_enforceable_rule(self) -> None:
        self.rules[0]["status"] = "experimental"
        self.write(self.record)
        self.assertTrue(any("exige regra active ou deprecated" in item for item in self.validate()))

    def test_rejects_missing_rule_condition_evidence(self) -> None:
        record = deepcopy(self.record)
        record["condition_evidence"] = []
        self.write(record)
        self.assertTrue(any("cobrir exatamente as condições" in item for item in self.validate()))

    def test_rejects_unbounded_exception(self) -> None:
        record = deepcopy(self.record)
        record["validity"] = {"expires_on": None, "review_condition": None}
        self.write(record)
        self.assertTrue(any("expires_on ou review_condition" in item for item in self.validate()))

    def test_rejects_expiry_before_decision(self) -> None:
        record = deepcopy(self.record)
        record["validity"]["expires_on"] = "2026-09-02"
        self.write(record)
        self.assertTrue(any("anterior a decision.decided_at" in item for item in self.validate()))

    def test_rejects_scope_outside_authorized_roots(self) -> None:
        record = deepcopy(self.record)
        record["scope"]["paths"] = ["infra/secrets"]
        self.write(record)
        self.assertTrue(any("fora das raízes autorizadas" in item for item in self.validate()))

    def test_rejects_evolutive_scope(self) -> None:
        record = deepcopy(self.record)
        record["scope"]["paths"] = [".evolutive/config.yaml"]
        self.write(record)
        self.assertTrue(any("não pode apontar para .evolutive" in item for item in self.validate()))

    def test_rejected_request_may_reference_rule_without_exceptions(self) -> None:
        record = deepcopy(self.record)
        record["rule_id"] = "ARCH-001"
        record["decision"]["outcome"] = "rejected"
        record["condition_evidence"] = []
        self.write(record)
        self.assertEqual(self.validate(), [])

    def test_rejects_symlinked_evolutive_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            target = Path(directory) / "external-governance"
            project.mkdir()
            target.mkdir()
            try:
                (project / ".evolutive").symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink indisponível neste ambiente: {exc}")

            resolved, failures = resolve_exception_directory(project)
            self.assertIsNone(resolved)
            self.assertTrue(any(".evolutive não pode ser link simbólico" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
