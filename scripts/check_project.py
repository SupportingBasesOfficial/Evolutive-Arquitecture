#!/usr/bin/env python3
"""Executa a conformidade sem misturar produtor, consumidor e verificador."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
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

    return {
        "report_format": 1,
        "mode": plan["mode"],
        "constitution": plan["constitution"],
        "rules": plan["rules"],
        "broker_audit": broker_audit,
        "checker_result": result,
        "isolation": {
            "producer_consumer_trees_disjoint": True,
            "project_root_disclosed_to_checker": False,
            "checker_received_only_brokered_files": True,
        },
    }


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
