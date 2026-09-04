#!/usr/bin/env python3
"""Valida taxonomia, profiles, capabilities e autoridade de semantic coverage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

if __package__:
    from .rule_semantic_coverage import (
        CAPABILITIES_SCHEMA,
        EVALUATOR_MANIFEST_SCHEMA,
        PROFILES_SCHEMA,
        RESULT_SCHEMA,
        TAXONOMY_SCHEMA,
        load_semantic_contracts,
        validate_evaluator_authority,
    )
else:
    from rule_semantic_coverage import (
        CAPABILITIES_SCHEMA,
        EVALUATOR_MANIFEST_SCHEMA,
        PROFILES_SCHEMA,
        RESULT_SCHEMA,
        TAXONOMY_SCHEMA,
        load_semantic_contracts,
        validate_evaluator_authority,
    )

ROOT = Path(__file__).resolve().parents[1]


def validate_schema(path: Path) -> list[str]:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return []
    except (OSError, ValueError) as exc:
        return [f"schema inválido {path.relative_to(ROOT).as_posix()}: {exc}"]


def validate_contract() -> list[str]:
    failures: list[str] = []
    for path in (
        TAXONOMY_SCHEMA,
        PROFILES_SCHEMA,
        CAPABILITIES_SCHEMA,
        RESULT_SCHEMA,
        EVALUATOR_MANIFEST_SCHEMA,
    ):
        failures.extend(validate_schema(path))
    if failures:
        return failures

    try:
        taxonomy, profiles, _ = load_semantic_contracts()
        manifest = validate_evaluator_authority()
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]

    if taxonomy["exhaustiveness"]["status"] != "not_established":
        failures.append("v0.1.0 exige taxonomia semanticamente não exaustiva")
    for profile in profiles["rules"]:
        if profile["profile_exhaustiveness"]["status"] != "not_established":
            failures.append(
                f"v0.1.0 exige profile semanticamente não exaustivo: {profile['rule_id']}"
            )

    authority = manifest["authority"]
    if authority["may_assert_complete_rule_semantics"] is not False:
        failures.append("evaluator v0.1.0 não pode afirmar complete_rule_semantics")
    if authority["may_produce_rule_pass"] is not False:
        failures.append("semantic coverage evaluator não pode produzir rule-pass")
    if authority["may_change_rule_status"] is not False:
        failures.append("semantic coverage evaluator não pode alterar rule status")

    result_schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
    complete_schema = result_schema["properties"]["rules"]["items"]["properties"]["complete_rule_semantics"]
    if complete_schema.get("const") is not False:
        failures.append("result schema v1 precisa fixar complete_rule_semantics=false")
    status_values = result_schema["properties"]["rules"]["items"]["properties"]["verdict"].get("enum", [])
    if "complete" in status_values:
        failures.append("result schema v1 não pode expor verdict complete")

    return failures


def main() -> int:
    failures = validate_contract()
    if failures:
        for failure in failures:
            print(f"ERRO: {failure}", file=sys.stderr)
        return 1
    print("OK: contratos de rule semantic coverage válidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
