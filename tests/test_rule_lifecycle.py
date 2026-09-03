from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

from scripts.validate_rule_lifecycle import DEFAULT_SCHEMA, validate_lifecycle


class RuleLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.rules = self.root / "rules"
        self.decisions = self.root / "decisions" / "rules"
        (self.rules / "universal").mkdir(parents=True)

        self.rule = {
            "id": "TEST-001",
            "status": "proposed",
            "introduced_in": "0.1.0",
        }
        self.write_rule()

        self.decision = {
            "rule_id": "TEST-001",
            "from_status": "proposed",
            "to_status": "experimental",
            "effective_in": "0.2.0",
            "motivation": "Validar a regra em adoção controlada antes de torná-la obrigatória.",
            "impact": {
                "compatibility": "compatible",
                "summary": "A regra passa a ser observada sem bloquear consumidores.",
            },
            "adoption": {
                "plan": "Executar em projetos-piloto e registrar falsos positivos e lacunas.",
                "transition": None,
            },
            "evidence": ["review:architecture-board/TEST-001"],
            "enforcement_readiness": {
                "state": "limited",
                "mechanism": "Checker de referência em modo informativo",
                "gaps": ["Cobertura de linguagens ainda parcial"],
            },
            "decision": {
                "outcome": "approved",
                "authority": "Architecture Board",
                "decided_at": "2026-09-03",
            },
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_rule(self) -> None:
        path = self.rules / "universal" / "TEST-001.yaml"
        path.write_text(
            yaml.safe_dump(self.rule, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def write_decision(self, decision: dict) -> None:
        directory = self.decisions / decision["rule_id"]
        directory.mkdir(parents=True, exist_ok=True)
        filename = (
            f"{decision['effective_in']}-{decision['to_status']}-"
            f"{decision['decision']['outcome']}.yaml"
        )
        (directory / filename).write_text(
            yaml.safe_dump(decision, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def validate(self, version: str = "0.2.0") -> list[str]:
        return validate_lifecycle(
            self.rules,
            self.decisions,
            DEFAULT_SCHEMA,
            version,
        )

    def test_proposed_rule_needs_no_decision(self) -> None:
        self.assertEqual(self.validate("0.1.0"), [])

    def test_approved_transition_must_match_declared_status(self) -> None:
        self.rule["status"] = "experimental"
        self.write_rule()
        self.write_decision(self.decision)
        self.assertEqual(self.validate(), [])

    def test_rejects_status_without_approved_chain(self) -> None:
        self.rule["status"] = "active"
        self.write_rule()
        failures = self.validate()
        self.assertTrue(any("cadeia aprovada termina em proposed" in item for item in failures))

    def test_rejected_decision_does_not_change_state(self) -> None:
        rejected = deepcopy(self.decision)
        rejected["decision"]["outcome"] = "rejected"
        self.write_decision(rejected)
        self.assertEqual(self.validate(), [])

    def test_active_promotion_requires_ready_enforcement(self) -> None:
        active = deepcopy(self.decision)
        active["to_status"] = "active"
        self.rule["status"] = "active"
        self.write_rule()
        self.write_decision(active)
        failures = self.validate()
        self.assertTrue(any("promoção para active exige" in item for item in failures))

    def test_rejects_broken_transition_chain(self) -> None:
        first = deepcopy(self.decision)
        self.rule["status"] = "active"
        self.write_rule()
        self.write_decision(first)

        second = deepcopy(self.decision)
        second["from_status"] = "proposed"
        second["to_status"] = "active"
        second["effective_in"] = "0.3.0"
        second["enforcement_readiness"]["state"] = "ready"
        second["enforcement_readiness"]["gaps"] = []
        self.write_decision(second)

        failures = self.validate("0.3.0")
        self.assertTrue(any("cadeia inválida" in item for item in failures))

    def test_rejects_future_effective_version(self) -> None:
        self.rule["status"] = "experimental"
        self.write_rule()
        future = deepcopy(self.decision)
        future["effective_in"] = "0.3.0"
        self.write_decision(future)
        failures = self.validate("0.2.0")
        self.assertTrue(any("está após VERSION" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
