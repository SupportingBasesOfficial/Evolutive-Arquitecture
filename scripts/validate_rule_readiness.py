#!/usr/bin/env python3
"""Valida avaliações auditáveis de prontidão das regras constitucionais."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = ROOT / "rules" / "universal"
DEFAULT_ASSESSMENTS = ROOT / "assessments" / "rules"
DEFAULT_SCHEMA = ROOT / "schema" / "rule-readiness.schema.json"


def location(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "<raiz>"


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: raiz YAML deve ser um objeto")
    return data


def validate_rule_readiness(
    rules_dir: Path = DEFAULT_RULES,
    assessments_dir: Path = DEFAULT_ASSESSMENTS,
    schema_path: Path = DEFAULT_SCHEMA,
) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    failures: list[str] = []
    rules: dict[str, dict] = {}
    for path in sorted(rules_dir.glob("*.yaml")):
        rule = load_yaml(path)
        rule_id = rule.get("id")
        if not isinstance(rule_id, str):
            failures.append(f"{path}: regra sem id válido")
            continue
        rules[rule_id] = rule

    if not assessments_dir.exists():
        return failures + [f"{assessments_dir}: diretório de avaliações ausente"]

    assessments: dict[str, dict] = {}
    for path in sorted(assessments_dir.iterdir()):
        if path.is_dir() or path.suffix != ".yaml":
            failures.append(f"{path}: somente arquivos YAML são permitidos")
            continue
        try:
            assessment = load_yaml(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            failures.append(str(exc))
            continue

        for error in sorted(
            validator.iter_errors(assessment),
            key=lambda item: [str(part) for part in item.absolute_path],
        ):
            failures.append(f"{path}:{location(error)}: {error.message}")

        rule_id = assessment.get("rule_id")
        if not isinstance(rule_id, str):
            continue
        if path.name != f"{rule_id}.yaml":
            failures.append(f"{path}: nome deve ser {rule_id}.yaml")
        if rule_id in assessments:
            failures.append(f"{path}: avaliação duplicada para {rule_id}")
        assessments[rule_id] = assessment

    missing = sorted(set(rules) - set(assessments))
    extra = sorted(set(assessments) - set(rules))
    for rule_id in missing:
        failures.append(f"avaliação ausente para {rule_id}")
    for rule_id in extra:
        failures.append(f"avaliação referencia regra inexistente: {rule_id}")

    for rule_id in sorted(set(rules) & set(assessments)):
        rule = rules[rule_id]
        assessment = assessments[rule_id]
        if assessment.get("assessed_status") != rule.get("status"):
            failures.append(
                f"{rule_id}: assessed_status diverge da regra: "
                f"{assessment.get('assessed_status')} != {rule.get('status')}"
            )

        declared_level = rule.get("enforcement", {}).get("level")
        if assessment.get("enforcement", {}).get("declared_level") != declared_level:
            failures.append(
                f"{rule_id}: declared_level diverge da regra: "
                f"{assessment.get('enforcement', {}).get('declared_level')} != {declared_level}"
            )

        exceptions_allowed = rule.get("exceptions", {}).get("allowed") is True
        exception_ready = assessment.get("criteria", {}).get("exception_governance_ready")
        if exceptions_allowed and exception_ready is not True:
            failures.append(
                f"{rule_id}: regra permite exceções e exige governança de exceção pronta"
            )

        verdict = assessment.get("verdict")
        target = assessment.get("target_status")
        criteria = assessment.get("criteria", {})
        enforcement = assessment.get("enforcement", {})

        experimental_minimum = all(
            criteria.get(name) is True
            for name in (
                "scope_is_observable",
                "compliance_is_observable",
                "evidence_collection_plan_exists",
                "exception_governance_ready",
            )
        )
        active_minimum = experimental_minimum and (
            criteria.get("enforcement_matches_declared_level") is True
            and enforcement.get("mechanism_available") is True
            and not enforcement.get("gaps")
        )

        if verdict == "experimental_ready":
            if target != "experimental":
                failures.append(f"{rule_id}: experimental_ready exige target_status experimental")
            if not experimental_minimum:
                failures.append(f"{rule_id}: critérios mínimos para experimental não atendidos")
        elif verdict == "active_ready":
            if target != "active":
                failures.append(f"{rule_id}: active_ready exige target_status active")
            if not active_minimum:
                failures.append(f"{rule_id}: critérios mínimos para active não atendidos")
            if enforcement.get("checker_outcomes") == "unknown_only":
                failures.append(f"{rule_id}: active_ready não pode depender apenas de outcome unknown")

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--assessments", type=Path, default=DEFAULT_ASSESSMENTS)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        failures = validate_rule_readiness(args.rules, args.assessments, args.schema)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Falha ao validar readiness: {exc}", file=sys.stderr)
        return 1

    if failures:
        print("Falha nas avaliações de readiness:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("OK: avaliações de readiness das regras estão consistentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
