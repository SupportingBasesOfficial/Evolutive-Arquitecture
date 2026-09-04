#!/usr/bin/env python3
"""Valida contratos estruturais de ecosystem discovery e observation alignment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ecosystem_inventory import load_catalog

SCHEMAS = [
    ROOT / "schema/ecosystem-catalog.schema.json",
    ROOT / "schema/ecosystem-discoverer-manifest.schema.json",
    ROOT / "schema/ecosystem-inventory.schema.json",
    ROOT / "schema/observation-aligner-manifest.schema.json",
    ROOT / "schema/observation-alignment.schema.json",
]
MANIFESTS = [
    (ROOT / "governance/ecosystem-discoverer.yaml", ROOT / "schema/ecosystem-discoverer-manifest.schema.json"),
    (ROOT / "governance/observation-aligner.yaml", ROOT / "schema/observation-aligner-manifest.schema.json"),
]


def validate_contract() -> list[str]:
    failures: list[str] = []
    schemas: dict[Path, dict] = {}
    for path in SCHEMAS:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schemas[path] = schema

    load_catalog()
    for manifest_path, schema_path in MANIFESTS:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        errors = sorted(
            Draft202012Validator(schemas[schema_path]).iter_errors(manifest),
            key=lambda item: [str(part) for part in item.absolute_path],
        )
        failures.extend(f"{manifest_path.name}: {error.message}" for error in errors)
    return failures


def main() -> int:
    try:
        failures = validate_contract()
    except (OSError, ValueError, KeyError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Falha ao validar ecosystem discovery: {exc}", file=sys.stderr)
        return 1
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("OK: contratos de ecosystem discovery e observation alignment estão consistentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
