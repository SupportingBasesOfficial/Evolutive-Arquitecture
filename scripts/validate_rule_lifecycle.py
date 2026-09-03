#!/usr/bin/env python3
"""Valida o ciclo de vida auditável das regras constitucionais."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_DIR = ROOT / "rules"
DEFAULT_DECISIONS_DIR = ROOT / "decisions" / "rules"
DEFAULT_SCHEMA = ROOT / "schema" / "rule-decision.schema.json"
VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
ALLOWED_TRANSITIONS = {
    "proposed": {"experimental", "active", "revoked"},
    "experimental": {"active", "revoked"},
    "active": {"deprecated", "revoked"},
    "deprecated": {"active", "revoked"},
    "revoked": set(),
}


def semver(value: str) -> tuple[int, int, int]:
    if not VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"versão semântica inválida: {value}")
    return tuple(int(part) for part in value.split("."))


def load_yaml(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def location(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "<raiz>"


def validate_lifecycle(
    rules_dir: Path,
    decisions_dir: Path,
    schema_path: Path,
    constitution_version: str,
) -> list[str]:
    current_version = semver(constitution_version)
    rules_dir = rules_dir.resolve()
    decisions_dir = decisions_dir.resolve()
    schema_path = schema_path.resolve()

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    failures: list[str] = []
    rules: dict[str, dict] = {}

    for path in sorted(rules_dir.rglob("*.yaml")):
        try:
            rule = load_yaml(path)
        except yaml.YAMLError as exc:
            failures.append(f"{path}: YAML inválido: {exc}")
            continue
        if not isinstance(rule, dict) or not isinstance(rule.get("id"), str):
            continue
        rules[rule["id"]] = rule
        introduced = rule.get("introduced_in")
        if isinstance(introduced, str):
            try:
                if semver(introduced) > current_version:
                    failures.append(
                        f"{path}: introduced_in {introduced} está após VERSION {constitution_version}."
                    )
            except ValueError as exc:
                failures.append(f"{path}: {exc}")

    decisions_by_rule: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    if decisions_dir.exists():
        for path in sorted(decisions_dir.rglob("*.yaml")):
            try:
                decision = load_yaml(path)
            except yaml.YAMLError as exc:
                failures.append(f"{path}: YAML inválido: {exc}")
                continue
            if not isinstance(decision, dict):
                failures.append(f"{path}: a raiz deve ser um objeto.")
                continue

            schema_errors = sorted(
                validator.iter_errors(decision),
                key=lambda item: [str(part) for part in item.absolute_path],
            )
            for error in schema_errors:
                failures.append(f"{path}:{location(error)}: {error.message}")
            if schema_errors:
                continue

            rule_id = decision["rule_id"]
            if rule_id not in rules:
                failures.append(f"{path}: rule_id {rule_id} não existe no catálogo.")
                continue

            expected_parent = decisions_dir / rule_id
            if path.parent != expected_parent:
                failures.append(
                    f"{path}: decisões de {rule_id} devem ficar em {expected_parent}."
                )

            expected_name = (
                f"{decision['effective_in']}-{decision['to_status']}-"
                f"{decision['decision']['outcome']}.yaml"
            )
            if path.name != expected_name:
                failures.append(f"{path}: o arquivo deve se chamar {expected_name}.")

            try:
                if semver(decision["effective_in"]) > current_version:
                    failures.append(
                        f"{path}: effective_in {decision['effective_in']} está após VERSION "
                        f"{constitution_version}."
                    )
            except ValueError as exc:
                failures.append(f"{path}: {exc}")

            if decision["to_status"] not in ALLOWED_TRANSITIONS[decision["from_status"]]:
                failures.append(
                    f"{path}: transição {decision['from_status']} -> "
                    f"{decision['to_status']} não é permitida."
                )

            if (
                decision["to_status"] == "active"
                and decision["decision"]["outcome"] == "approved"
                and decision["enforcement_readiness"]["state"] != "ready"
            ):
                failures.append(
                    f"{path}: promoção para active exige enforcement_readiness.state=ready."
                )

            decisions_by_rule[rule_id].append((path, decision))

    for rule_id, rule in sorted(rules.items()):
        approved = [
            (path, decision)
            for path, decision in decisions_by_rule.get(rule_id, [])
            if decision["decision"]["outcome"] == "approved"
        ]
        approved.sort(key=lambda item: (semver(item[1]["effective_in"]), item[0].name))

        state = "proposed"
        seen_versions: set[str] = set()
        for path, decision in approved:
            version = decision["effective_in"]
            if version in seen_versions:
                failures.append(
                    f"{path}: mais de uma transição aprovada de {rule_id} em {version}."
                )
            seen_versions.add(version)

            if decision["from_status"] != state:
                failures.append(
                    f"{path}: cadeia inválida; estado anterior calculado é {state}, "
                    f"mas from_status declara {decision['from_status']}."
                )
                continue
            state = decision["to_status"]

        declared = rule.get("status")
        if declared != state:
            failures.append(
                f"{rule_id}: status declarado é {declared}, mas a cadeia aprovada termina em {state}."
            )

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-dir", type=Path, default=DEFAULT_RULES_DIR)
    parser.add_argument("--decisions-dir", type=Path, default=DEFAULT_DECISIONS_DIR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--version",
        default=(ROOT / "VERSION").read_text(encoding="ascii").strip(),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        failures = validate_lifecycle(
            args.rules_dir,
            args.decisions_dir,
            args.schema,
            args.version,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Falha ao validar ciclo de vida: {exc}", file=sys.stderr)
        return 1

    if failures:
        print("Falha na validação do ciclo de vida das regras:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("OK: estados das regras correspondem às decisões aprovadas e auditáveis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
