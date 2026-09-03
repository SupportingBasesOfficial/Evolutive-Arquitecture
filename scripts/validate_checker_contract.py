#!/usr/bin/env python3
"""Valida o manifesto e os schemas fechados do contrato de verificadores."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = ROOT / "schema" / "checker-manifest.schema.json"
REQUEST_SCHEMA = ROOT / "schema" / "checker-request.schema.json"
RESULT_SCHEMA = ROOT / "schema" / "checker-result.schema.json"
MANIFEST_TEMPLATE = ROOT / "templates" / "checker-manifest.yaml"


def load_schema(path: Path) -> dict:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def catalog_rule_ids(root: Path = ROOT) -> set[str]:
    result = set()
    for path in (root / "rules").rglob("*.yaml"):
        rule = yaml.safe_load(path.read_text(encoding="utf-8"))
        result.add(rule["id"])
    return result


def validate_manifest(path: Path = MANIFEST_TEMPLATE) -> list[str]:
    schema = load_schema(MANIFEST_SCHEMA)
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    failures = [error.message for error in validator.iter_errors(manifest)]
    if failures:
        return failures

    unknown = sorted(set(manifest["rules"]) - catalog_rule_ids())
    if unknown:
        failures.append("regras desconhecidas: " + ", ".join(unknown))
    return failures


def main() -> int:
    for path in (MANIFEST_SCHEMA, REQUEST_SCHEMA, RESULT_SCHEMA):
        load_schema(path)

    failures = validate_manifest()
    if failures:
        print("Contrato de verificador inválido:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("OK: schemas fechados e manifesto de exemplo válidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
