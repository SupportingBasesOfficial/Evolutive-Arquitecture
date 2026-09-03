#!/usr/bin/env python3
"""Valida a política de governança do repositório e sua ligação com o CI canônico."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "governance" / "repository.yaml"
DEFAULT_SCHEMA = ROOT / "schema" / "repository-governance.schema.json"
DEFAULT_WORKFLOW = ROOT / ".github" / "workflows" / "validate-rules.yml"


def location(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "<raiz>"


def load_yaml(path: Path) -> dict:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: raiz YAML deve ser um objeto")
    return data


def expected_check_names(workflow: dict) -> set[str]:
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        raise ValueError("workflow canônico não possui jobs")

    job = jobs.get("validate")
    if not isinstance(job, dict):
        raise ValueError("workflow canônico deve manter o job 'validate'")

    strategy = job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    os_values = matrix.get("os") if isinstance(matrix, dict) else None
    if not isinstance(os_values, list) or not os_values:
        raise ValueError("job 'validate' deve possuir matrix.os não vazia")

    return {f"validate ({value})" for value in os_values}


def validate_repository_governance(
    policy_path: Path = DEFAULT_POLICY,
    schema_path: Path = DEFAULT_SCHEMA,
    workflow_path: Path = DEFAULT_WORKFLOW,
) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    if not isinstance(policy, dict):
        return [f"{policy_path}: raiz YAML deve ser um objeto"]

    validator = Draft202012Validator(schema)
    failures = [
        f"{policy_path}:{location(error)}: {error.message}"
        for error in sorted(
            validator.iter_errors(policy),
            key=lambda item: [str(part) for part in item.absolute_path],
        )
    ]
    if failures:
        return failures

    workflow = load_yaml(workflow_path)
    triggers = workflow.get("on")
    if not isinstance(triggers, dict):
        failures.append("workflow canônico deve declarar gatilhos explícitos")
    else:
        if "pull_request" not in triggers:
            failures.append("workflow canônico deve executar em pull_request")
        push = triggers.get("push")
        branches = push.get("branches") if isinstance(push, dict) else None
        if not isinstance(branches, list) or "main" not in branches:
            failures.append("workflow canônico deve executar em push para main")

    declared_checks = set(policy["main_branch"]["required_status_checks"])
    produced_checks = expected_check_names(workflow)
    if declared_checks != produced_checks:
        failures.append(
            "required_status_checks divergem dos checks produzidos pelo workflow: "
            f"declarados={sorted(declared_checks)}, produzidos={sorted(produced_checks)}"
        )

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        failures = validate_repository_governance(
            args.policy,
            args.schema,
            args.workflow,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Falha ao validar governança do repositório: {exc}", file=sys.stderr)
        return 1

    if failures:
        print("Falha na governança do repositório:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("OK: contrato interno de governança do repositório está consistente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
