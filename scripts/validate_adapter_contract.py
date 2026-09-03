#!/usr/bin/env python3
"""Valida manifesto, request e result de adapters de ecossistema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = ROOT / "schema" / "adapter-manifest.schema.json"
REQUEST_SCHEMA = ROOT / "schema" / "adapter-request.schema.json"
RESULT_SCHEMA = ROOT / "schema" / "adapter-result.schema.json"
MANIFEST_TEMPLATE = ROOT / "adapters" / "python-imports.yaml"


def schema_failures(path: Path, instance: dict) -> list[str]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return [error.message for error in Draft202012Validator(schema).iter_errors(instance)]


def validate_manifest(path: Path = MANIFEST_TEMPLATE) -> list[str]:
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    failures = schema_failures(MANIFEST_SCHEMA, manifest)
    if not isinstance(manifest, dict):
        return failures + ["manifesto deve ser objeto"]
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    if manifest.get("constitution_version") != version:
        failures.append("constitution_version do adapter diverge da Constituição")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_TEMPLATE)
    args = parser.parse_args()
    try:
        failures = validate_manifest(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Falha ao validar adapter: {exc}", file=sys.stderr)
        return 1
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("OK: contrato do adapter está consistente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
