#!/usr/bin/env python3
"""Valida schemas, manifesto e autoridade da coverage attestation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.coverage_attestation import (
    ATTESTOR_ID,
    ATTESTOR_MANIFEST_SCHEMA,
    ATTESTOR_VERSION,
    validate_attestor_authority,
)

EVIDENCE_SCHEMA = ROOT / "schema" / "architecture-evidence.schema.json"
ATTESTATION_SCHEMA = ROOT / "schema" / "coverage-attestation.schema.json"


def validate_contract() -> list[str]:
    failures: list[str] = []
    loaded: dict[Path, dict] = {}
    for path in (EVIDENCE_SCHEMA, ATTESTATION_SCHEMA, ATTESTOR_MANIFEST_SCHEMA):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        loaded[path] = schema

    attestation = loaded[ATTESTATION_SCHEMA]
    evaluator = attestation["properties"]["evaluator"]["properties"]
    if evaluator["id"].get("const") != ATTESTOR_ID:
        failures.append("schema diverge do ATTESTOR_ID da implementação")
    if evaluator["version"].get("const") != ATTESTOR_VERSION:
        failures.append("schema diverge da ATTESTOR_VERSION da implementação")

    try:
        validate_attestor_authority()
    except ValueError as exc:
        failures.append(str(exc))
    return failures


def main() -> int:
    try:
        failures = validate_contract()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Falha ao validar coverage attestation: {exc}", file=sys.stderr)
        return 1
    if failures:
        print("Contrato de coverage attestation inválido:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("OK: schemas, manifesto, digest e autoridade da coverage attestation estão consistentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
