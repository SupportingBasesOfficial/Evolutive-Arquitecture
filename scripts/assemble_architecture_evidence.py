#!/usr/bin/env python3
"""Combina política, broker audit e resultado de adapter em evidência canônica."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

if __package__:
    from .architecture_policy import is_within, load_architecture_policy
    from .validate_adapter_contract import RESULT_SCHEMA, schema_failures, validate_manifest
else:
    from architecture_policy import is_within, load_architecture_policy
    from validate_adapter_contract import RESULT_SCHEMA, schema_failures, validate_manifest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_SCHEMA = ROOT / "schema" / "architecture-evidence.schema.json"


def validate_broker_binding(result: dict, broker_audit: dict) -> None:
    required = {
        "broker_version",
        "files_considered",
        "files_delivered",
        "bytes_read",
        "inventory_sha256",
        "delivered_content_sha256",
        "skipped",
        "project_root_disclosed",
    }
    if set(broker_audit) != required:
        raise ValueError("broker_audit possui estrutura inesperada")
    if broker_audit["broker_version"] != 1:
        raise ValueError("broker_version não suportado")
    if broker_audit["project_root_disclosed"] is not False:
        raise ValueError("broker_audit indica divulgação da raiz")
    for field in ("inventory_sha256", "delivered_content_sha256"):
        value = broker_audit[field]
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"{field} inválido")
    coverage = result["coverage"]
    if broker_audit["files_delivered"] != coverage["files_received"]:
        raise ValueError("coverage do adapter diverge de files_delivered do broker")
    if broker_audit["bytes_read"] != coverage["bytes_received"]:
        raise ValueError("coverage do adapter diverge de bytes_read do broker")


def assemble_evidence(
    config_path: Path,
    project_root: Path,
    manifest_path: Path,
    result: dict,
    broker_audit: dict,
) -> dict:
    manifest_failures = validate_manifest(manifest_path)
    if manifest_failures:
        raise ValueError("manifesto inválido: " + "; ".join(manifest_failures))
    result_failures = schema_failures(RESULT_SCHEMA, result)
    if result_failures:
        raise ValueError("resultado inválido: " + "; ".join(result_failures))
    validate_broker_binding(result, broker_audit)

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    policy = load_architecture_policy(config_path, project_root)
    if result["adapter_id"] != manifest["id"] or result["adapter_version"] != manifest["version"]:
        raise ValueError("resultado não corresponde ao manifesto do adapter")
    if result["ecosystem"] != manifest["ecosystem"]:
        raise ValueError("ecossistema do resultado diverge do manifesto")
    if manifest["constitution_version"] != policy["constitution_version"]:
        raise ValueError("adapter não está autorizado para a versão da política")

    components = {item["id"]: item for item in policy["components"]}
    for edge in result["dependencies"]:
        source = components.get(edge["source_component"])
        target = components.get(edge["target_component"])
        if source is None or target is None:
            raise ValueError("adapter observou componente fora da política")
        if not any(is_within(edge["source_path"], root) for root in source["roots"]):
            raise ValueError("adapter observou source_path fora do componente declarado")
        if not any(is_within(edge["target_path"], root) for root in target["roots"]):
            raise ValueError("adapter observou target_path fora do componente declarado")

    evidence = {
        "evidence_version": 1,
        "constitution_version": policy["constitution_version"],
        "producer": {
            "kind": "adapter",
            "id": result["adapter_id"],
            "version": result["adapter_version"],
        },
        "observation": {
            "ecosystem": result["ecosystem"],
            "coverage": result["coverage"],
            "broker_audit": broker_audit,
            "errors": result["errors"],
        },
        "graph": {
            "components": policy["components"],
            "dependencies": result["dependencies"],
        },
    }
    schema = json.loads(EVIDENCE_SCHEMA.read_text(encoding="utf-8"))
    errors = [error.message for error in Draft202012Validator(schema).iter_errors(evidence)]
    if errors:
        raise ValueError("evidência montada é inválida: " + "; ".join(errors))
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("execution", type=Path, help="JSON com result e broker_audit")
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        execution = json.loads(args.execution.read_text(encoding="utf-8"))
        evidence = assemble_evidence(
            args.config,
            args.project_root,
            args.manifest,
            execution["result"],
            execution["broker_audit"],
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Falha ao montar evidência arquitetural: {exc}", file=sys.stderr)
        return 1
    print(yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
