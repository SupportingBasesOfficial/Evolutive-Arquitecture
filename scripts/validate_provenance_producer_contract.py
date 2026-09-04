#!/usr/bin/env python3
"""Valida schemas e autoridades do producer confiável de provenance."""

from __future__ import annotations

import json
import sys

from jsonschema import Draft202012Validator

from provenance_producer_trust import (
    ATTESTATION_SCHEMA,
    ATTESTOR_MANIFEST_SCHEMA,
    MANIFEST_SCHEMA,
    validate_attestor_authority,
    validate_producer_manifest,
)


def main() -> int:
    try:
        for path in (MANIFEST_SCHEMA, ATTESTATION_SCHEMA, ATTESTOR_MANIFEST_SCHEMA):
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        validate_attestor_authority()
        validate_producer_manifest()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    print("OK: contrato de provenance producer confiável válido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
