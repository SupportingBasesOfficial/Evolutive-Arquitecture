#!/usr/bin/env python3
"""Valida todas as regras canônicas do repositório."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "rule.schema.json"
RULES_DIR = ROOT / "rules"
VALID_LAYERS = {"universal", "project", "technology", "platform"}


def location(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "<raiz>"


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    paths = sorted(RULES_DIR.rglob("*.yaml"))
    if not paths:
        print("ERRO: nenhuma regra encontrada em rules/.", file=sys.stderr)
        return 1

    failures: list[str] = []
    seen_ids: dict[str, Path] = {}

    for path in paths:
        relative = path.relative_to(ROOT)
        try:
            rule = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            failures.append(f"{relative}: YAML inválido: {exc}")
            continue

        if not isinstance(rule, dict):
            failures.append(f"{relative}: a raiz deve ser um objeto.")
            continue

        for error in sorted(validator.iter_errors(rule), key=lambda item: list(item.absolute_path)):
            failures.append(f"{relative}:{location(error)}: {error.message}")

        rule_id = rule.get("id")
        if isinstance(rule_id, str):
            if path.stem != rule_id:
                failures.append(
                    f"{relative}: o arquivo deve se chamar {rule_id}.yaml."
                )
            if rule_id in seen_ids:
                failures.append(
                    f"{relative}: ID duplicado; já declarado em "
                    f"{seen_ids[rule_id].relative_to(ROOT)}."
                )
            else:
                seen_ids[rule_id] = path

        try:
            layer_dir = relative.parts[1]
        except IndexError:
            failures.append(f"{relative}: caminho de regra incompleto.")
        else:
            if layer_dir not in VALID_LAYERS:
                failures.append(f"{relative}: diretório de camada desconhecido.")
            elif rule.get("layer") != layer_dir:
                failures.append(
                    f"{relative}: layer deve ser '{layer_dir}' para este diretório."
                )

    if failures:
        print("Falha na validação das regras:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"OK: {len(paths)} regra(s) válida(s), com IDs únicos e caminhos coerentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
