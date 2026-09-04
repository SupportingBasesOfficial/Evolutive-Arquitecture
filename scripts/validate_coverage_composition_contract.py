#!/usr/bin/env python3
"""Valida schemas, manifesto e autoridade do coverage composer."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.coverage_composition import COMPOSER_ID, COMPOSER_VERSION
from scripts.run_adapter import canonical_bytes

OBSERVATION_POLICY_SCHEMA = ROOT / "schema" / "observation-policy.schema.json"
COMPOSITION_SCHEMA = ROOT / "schema" / "coverage-composition.schema.json"
COMPOSER_MANIFEST_SCHEMA = ROOT / "schema" / "coverage-composer-manifest.schema.json"
COMPOSER_MANIFEST = ROOT / "governance" / "coverage-composer.yaml"
IMPLEMENTATION = ROOT / "scripts" / "coverage_composition.py"


def validate_contract() -> list[str]:
    failures: list[str] = []
    for path in (OBSERVATION_POLICY_SCHEMA, COMPOSITION_SCHEMA, COMPOSER_MANIFEST_SCHEMA):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)

    manifest_schema = json.loads(COMPOSER_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    manifest = yaml.safe_load(COMPOSER_MANIFEST.read_text(encoding="utf-8"))
    failures.extend(error.message for error in Draft202012Validator(manifest_schema).iter_errors(manifest))
    if failures:
        return failures

    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    if manifest["id"] != COMPOSER_ID:
        failures.append("manifesto diverge do COMPOSER_ID da implementação")
    if manifest["version"] != COMPOSER_VERSION:
        failures.append("manifesto diverge da COMPOSER_VERSION da implementação")
    if manifest["constitution_version"] != version:
        failures.append("constitution_version do composer diverge da Constituição")
    actual = hashlib.sha256(canonical_bytes(IMPLEMENTATION)).hexdigest()
    if manifest["implementation_sha256"] != actual:
        failures.append(f"implementation_sha256 do coverage composer diverge: actual={actual}")
    if manifest["authority"]["composition_only"] is not True:
        failures.append("coverage composer deve possuir authority composition_only")
    if manifest["authority"]["may_change_checker_outcome"] is not False:
        failures.append("coverage composer não pode alterar checker outcome")
    if manifest["authority"]["ecosystem_discovery"] is not False:
        failures.append("coverage composer 0.1.0 não pode alegar ecosystem discovery")
    return failures


def main() -> int:
    try:
        failures = validate_contract()
    except (OSError, ValueError, KeyError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Falha ao validar coverage composition: {exc}", file=sys.stderr)
        return 1
    if failures:
        print("Contrato de coverage composition inválido:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("OK: observation policy, composition schema e coverage composer estão consistentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
