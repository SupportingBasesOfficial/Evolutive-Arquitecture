#!/usr/bin/env python3
"""Valida o contrato e a autoridade do semantic provenance interpreter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator

from scripts.provenance_semantic_interpretation import (
    INTERPRETER_MANIFEST_SCHEMA,
    RESULT_SCHEMA,
    validate_interpreter_contract,
)


def main() -> int:
    try:
        for path in (INTERPRETER_MANIFEST_SCHEMA, RESULT_SCHEMA):
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        validate_interpreter_contract()
    except (OSError, ValueError, json.JSONDecodeError, KeyError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    print("OK: contrato de provenance semantic interpretation válido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
