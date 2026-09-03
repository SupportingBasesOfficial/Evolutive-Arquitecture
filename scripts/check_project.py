#!/usr/bin/env python3
"""Executa a conformidade sem misturar produtor, consumidor e verificador."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REPORT_SCHEMA = REPOSITORY_ROOT / "schema" / "conformance-report.schema.json"
CHECKER_RESULT_SCHEMA = REPOSITORY_ROOT / "schema" / "checker-result.schema.json"

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

if __package__:
    from .content_broker import build_checker_request
    from .plan_compliance import build_plan
    from .run_checker import execute_checker
else:
    from content_broker import build_checker_request
    from plan_compliance import build_plan
    from run_checker import execute_checker


def is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
        return True
    except ValueError:
        return False


def require_disjoint_trees(project_root: Path, constitution_root: Path) -> None:
    project = project_root.resolve()
    constitution = constitution_root.resolve()
    if is_within(project, constitution) or is_within(constitution, project):
        raise ValueError(
            "projeto consumidor e repositório da Constituição devem usar "
            "árvores de diretórios separadas"
        )


def canonical_sha256(value: dict) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_pipeline_consistency(request: dict, audit: dict, result: dict) -> None:
    delivered_files = len(request["files"])
    delivered_bytes = sum(item["size_bytes"] for item in request["files"])

    if audit["files_delivered"] != delivered_files:
        raise ValueError("auditoria do broker diverge da requisição entregue")
    if audit["bytes_read"] != delivered_bytes:
        raise ValueError("bytes da auditoria divergem da requisição entregue")
    if result["metrics"]["files_received"] != delivered_files:
        raise ValueError("métrica de arquivos do verificador diverge da requisição")
    if result["metrics"]["bytes_received"] != delivered_bytes:
        raise ValueError("métrica de bytes do verificador diverge da requisição")


def validate_report(report: dict) -> list[str]:
    schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
    checker_schema = json.loads(CHECKER_RESULT_SCHEMA.read_text(encoding="utf-8"))
    registry = Registry().with_resource(
        checker_schema["$id"],
        Resource.from_contents(checker_schema),
    )
    validator = Draft202012Validator(schema, registry=registry)
    return [
        error.message
        for error in sorted(validator.iter_errors(report), key=lambda item: list(item.path))
    ]


def run_conformance(
    config_path: Path,
    project_root: Path,
    bundle_path: Path,
    manifest_path: Path,
    *,
    constitution_root: Path = REPOSITORY_ROOT,
) -> dict:
    require_disjoint_trees(project_root, constitution_root)

    plan = build_plan(config_path, project_root, bundle_path)
    request, broker_audit = build_checker_request(
        config_path,
        project_root,
        manifest_path,
    )
    result = execute_checker(manifest_path, request)
    verify_pipeline_consistency(request, broker_audit, result)

    report = {
        "report_format": 1,
        "mode": plan["mode"],
        "constitution": plan["constitution"],
        "rules": plan["rules"],
        "broker_audit": broker_audit,
        "checker_result": result,
        "provenance": {
            "request_sha256": canonical_sha256(request),
            "checker_manifest_sha256": hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest(),
        },
        "isolation": {
            "producer_consumer_trees_disjoint": True,
            "project_root_disclosed_to_checker": False,
            "checker_received_only_brokered_files": True,
        },
    }
    failures = validate_report(report)
    if failures:
        raise ValueError("relatório inválido: " + "; ".join(failures))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_conformance(
            args.config,
            args.project_root,
            args.bundle,
            args.manifest,
        )
    except (OSError, ValueError, KeyError) as exc:
        print(f"Falha ao executar conformidade: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
