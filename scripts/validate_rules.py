#!/usr/bin/env python3
"""Valida um catálogo de regras sem inspecionar o projeto consumidor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = REPOSITORY_ROOT / "schema" / "rule.schema.json"
DEFAULT_RULES_DIR = REPOSITORY_ROOT / "rules"
VALID_LAYERS = {"universal", "project", "technology", "platform"}


def location(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "<raiz>"


def validate_catalog(schema_path: Path, rules_dir: Path) -> list[str]:
    """Retorna violações encontradas exclusivamente dentro de rules_dir."""
    schema_path = schema_path.resolve()
    rules_dir = rules_dir.resolve()

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    paths = sorted(rules_dir.rglob("*.yaml"))
    if not paths:
        return [f"{rules_dir}: nenhuma regra encontrada."]

    failures: list[str] = []
    seen_ids: dict[str, Path] = {}

    for path in paths:
        relative = path.relative_to(rules_dir.parent)
        try:
            rule = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            failures.append(f"{relative}: YAML inválido: {exc}")
            continue

        if not isinstance(rule, dict):
            failures.append(f"{relative}: a raiz deve ser um objeto.")
            continue

        for error in sorted(
            validator.iter_errors(rule),
            key=lambda item: [str(part) for part in item.absolute_path],
        ):
            failures.append(f"{relative}:{location(error)}: {error.message}")

        rule_id = rule.get("id")
        if isinstance(rule_id, str):
            if path.stem != rule_id:
                failures.append(f"{relative}: o arquivo deve se chamar {rule_id}.yaml.")
            if rule_id in seen_ids:
                first = seen_ids[rule_id].relative_to(rules_dir.parent)
                failures.append(f"{relative}: ID duplicado; já declarado em {first}.")
            else:
                seen_ids[rule_id] = path

        layer_dir = path.relative_to(rules_dir).parts[0]
        if layer_dir not in VALID_LAYERS:
            failures.append(f"{relative}: diretório de camada desconhecido.")
        elif rule.get("layer") != layer_dir:
            failures.append(
                f"{relative}: layer deve ser '{layer_dir}' para este diretório."
            )

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida somente o catálogo indicado; não percorre a raiz do projeto."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--rules-dir", type=Path, default=DEFAULT_RULES_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures = validate_catalog(args.schema, args.rules_dir)

    if failures:
        print("Falha na validação das regras:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    count = len(list(args.rules_dir.resolve().rglob("*.yaml")))
    print(f"OK: {count} regra(s) válida(s), com IDs únicos e caminhos coerentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
