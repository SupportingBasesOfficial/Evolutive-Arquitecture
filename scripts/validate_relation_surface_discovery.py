#!/usr/bin/env python3
"""Valida o contrato canônico de relation surface discovery."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.relation_surface_discovery import (
    DESCRIPTOR_SCHEMA,
    MANIFEST_SCHEMA,
    RESULT_SCHEMA,
    _load_json,
    validate_discoverer_authority,
)
from jsonschema import Draft202012Validator


def validate() -> None:
    for schema_path in (MANIFEST_SCHEMA, DESCRIPTOR_SCHEMA, RESULT_SCHEMA):
        Draft202012Validator.check_schema(_load_json(schema_path))
    validate_discoverer_authority()


def main() -> int:
    try:
        validate()
    except (OSError, ValueError, KeyError) as exc:
        print(f"Falha no contrato de relation surface discovery: {exc}", file=sys.stderr)
        return 1
    print("OK: relation surface discovery contract válido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
