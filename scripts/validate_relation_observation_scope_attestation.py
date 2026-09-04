#!/usr/bin/env python3
"""Valida os contratos da relation observation scope attestation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.relation_observation_scope_attestation import validate_scope_attestor_authority

SCHEMAS = [
    ROOT / "schema" / "relation-observation-scope.schema.json",
    ROOT / "schema" / "relation-observation-scope-attestation.schema.json",
    ROOT / "schema" / "relation-observation-scope-attestor-manifest.schema.json",
]


def validate_contract() -> list[str]:
    failures: list[str] = []
    for path in SCHEMAS:
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except (OSError, ValueError) as exc:
            failures.append(f"{path.relative_to(ROOT)}: {exc}")
    try:
        validate_scope_attestor_authority()
    except (OSError, ValueError, KeyError) as exc:
        failures.append(str(exc))
    return failures


def main() -> int:
    failures = validate_contract()
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("OK: relation observation scope attestation contract valido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
