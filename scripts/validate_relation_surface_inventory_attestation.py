#!/usr/bin/env python3
"""Valida schemas, manifesto e identidade do relation surface inventory attestor."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.relation_surface_inventory_attestation import (  # noqa: E402
    ATTESTATION_SCHEMA,
    DECLARATION_SCHEMA,
    MANIFEST_SCHEMA,
    validate_attestor_authority,
)


def main() -> int:
    try:
        for path in (MANIFEST_SCHEMA, DECLARATION_SCHEMA, ATTESTATION_SCHEMA):
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        validate_attestor_authority()
    except (OSError, ValueError, KeyError) as exc:
        print(f"Falha no relation surface inventory attestation contract: {exc}", file=sys.stderr)
        return 1
    print("OK: relation surface inventory attestation contract válido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
