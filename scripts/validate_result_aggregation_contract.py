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
        evidence = profile["positive_evidence"]
        if evidence["claim_scope"] != "observed_dependency_graph":
            failures.append(f"positive profile de {rule_id} usa claim_scope não autorizado")
        if evidence["complete_rule_semantics"] is not False:
            failures.append(f"positive profile de {rule_id} não pode alegar semântica completa nesta versão")

    authority = manifest["authority"]
    if authority["may_change_rule_status"] is not False:
        failures.append("aggregator não pode promover status normativo")
    if authority["may_mutate_checker_result"] is not False:
        failures.append("aggregator não pode mutar checker result")
    if authority["may_produce_positive_evidence"] is not True:
        failures.append("autoridade de positive evidence deve ser explícita")
    if authority["may_produce_rule_pass"] is not False:
        failures.append("aggregator 0.1.0 não pode possuir autoridade de conformidade normativa positiva")

    result_schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
    statuses = result_schema["properties"]["outcomes"]["items"]["properties"]["status"]["enum"]
    if statuses != ["fail", "unknown"]:
        failures.append("resultado agregado 0.1.0 deve limitar status a fail/unknown")

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
