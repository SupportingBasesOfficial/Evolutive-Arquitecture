#!/usr/bin/env python3
"""Valida o contrato do semantic relation evidence aggregator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.semantic_relation_evidence_aggregation import (
    RESULT_SCHEMA,
    validate_aggregator_authority,
)


def main() -> int:
    try:
        schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validate_aggregator_authority()
    except (OSError, ValueError, KeyError) as exc:
        print(f"Falha no contrato de semantic relation evidence aggregation: {exc}", file=sys.stderr)
        return 1
    print("OK: contrato de semantic relation evidence aggregation válido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
