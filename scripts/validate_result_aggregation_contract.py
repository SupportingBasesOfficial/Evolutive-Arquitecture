#!/usr/bin/env python3
"""Valida contratos e autoridades do trusted result aggregator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

if __package__:
    from .result_aggregation import (
        AGGREGATOR_ID,
        AGGREGATOR_VERSION,
        AGGREGATOR_MANIFEST,
        AGGREGATOR_MANIFEST_SCHEMA,
        POLICY_PATH,
        POLICY_SCHEMA,
        RESULT_SCHEMA,
        load_positive_policy,
        validate_aggregator_authority,
    )
else:
    from result_aggregation import (
        AGGREGATOR_ID,
        AGGREGATOR_VERSION,
        AGGREGATOR_MANIFEST,
        AGGREGATOR_MANIFEST_SCHEMA,
        POLICY_PATH,
        POLICY_SCHEMA,
        RESULT_SCHEMA,
        load_positive_policy,
        validate_aggregator_authority,
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
    for path in (RESULT_SCHEMA, POLICY_SCHEMA, AGGREGATOR_MANIFEST_SCHEMA):
        failures.extend(validate_schema(path))
    if failures:
        return failures

    try:
        manifest = validate_aggregator_authority()
        policy = load_positive_policy()
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]

    if manifest["id"] != AGGREGATOR_ID or manifest["version"] != AGGREGATOR_VERSION:
        failures.append("manifesto do aggregator diverge das constantes da implementação")

    rule_files = {
        yaml.safe_load(path.read_text(encoding="utf-8"))["id"]: path
        for path in sorted((ROOT / "rules").glob("**/*.yaml"))
    }
    for profile in policy["rules"]:
        rule_id = profile["rule_id"]
        if rule_id not in rule_files:
            failures.append(f"positive result policy referencia regra inexistente: {rule_id}")

    raw_manifest = yaml.safe_load(AGGREGATOR_MANIFEST.read_text(encoding="utf-8"))
    if raw_manifest["authority"]["may_change_rule_status"] is not False:
        failures.append("aggregator não pode promover status normativo")
    if raw_manifest["authority"]["may_mutate_checker_result"] is not False:
        failures.append("aggregator não pode mutar checker result")
    if raw_manifest["authority"]["may_produce_derived_pass"] is not True:
        failures.append("autoridade de derived pass deve ser explícita")

    return failures


def main() -> int:
    failures = validate_contract()
    if failures:
        for failure in failures:
            print(f"ERRO: {failure}", file=sys.stderr)
        return 1
    print("OK: contratos de trusted result aggregation válidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
