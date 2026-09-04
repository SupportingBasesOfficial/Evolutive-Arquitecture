#!/usr/bin/env python3
"""Valida a matriz declarativa de observações arquiteturais do consumidor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator

if __package__:
    from .validate_adapter_contract import CANONICAL_MANIFESTS, validate_manifest
    from .validate_project_config import DEFAULT_SCHEMA as PROJECT_CONFIG_SCHEMA, validate_config
else:
    from validate_adapter_contract import CANONICAL_MANIFESTS, validate_manifest
    from validate_project_config import DEFAULT_SCHEMA as PROJECT_CONFIG_SCHEMA, validate_config

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schema" / "observation-policy.schema.json"
POLICY_RELATIVE_PATH = PurePosixPath(".evolutive/observation-policy.yaml")


def schema_location(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "<raiz>"


def canonical_manifests_by_id() -> dict[str, tuple[Path, dict]]:
    by_id: dict[str, tuple[Path, dict]] = {}
    for path in sorted(CANONICAL_MANIFESTS.glob("*.yaml")):
        failures = validate_manifest(path)
        if failures:
            raise ValueError(
                f"manifesto canônico inválido {path.relative_to(ROOT).as_posix()}: "
                + "; ".join(failures)
            )
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        adapter_id = manifest["id"]
        if adapter_id in by_id:
            raise ValueError(f"adapter id canônico duplicado: {adapter_id}")
        by_id[adapter_id] = (path, manifest)
    return by_id


def validate_observation_policy(
    config_path: Path,
    project_root: Path,
    schema_path: Path = DEFAULT_SCHEMA,
) -> tuple[dict | None, list[str]]:
    config_failures = validate_config(config_path, PROJECT_CONFIG_SCHEMA)
    if config_failures:
        return None, ["configuração inválida: " + item for item in config_failures]

    project_root = project_root.resolve()
    evolutive = project_root / ".evolutive"
    policy_path = project_root / POLICY_RELATIVE_PATH.as_posix()
    if evolutive.is_symlink():
        return None, [".evolutive não pode ser link simbólico"]
    if not policy_path.exists():
        return None, ["observation-policy.yaml ausente"]
    if policy_path.is_symlink():
        return None, ["observation-policy.yaml não pode ser link simbólico"]
    try:
        policy_path.resolve().relative_to(project_root)
    except ValueError:
        return None, ["observation-policy.yaml escapou da raiz do projeto"]

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    try:
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, [f"YAML inválido: {exc}"]

    errors = sorted(
        Draft202012Validator(schema).iter_errors(policy),
        key=lambda item: [str(part) for part in item.absolute_path],
    )
    failures = [f"{schema_location(error)}: {error.message}" for error in errors]
    if errors or not isinstance(policy, dict):
        return None, failures

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if policy["constitution_version"] != config["constitution"]["version"]:
        failures.append("constitution_version diverge da versão constitucional do consumidor")

    manifests = canonical_manifests_by_id()
    seen: set[str] = set()
    for observation in policy["required_observations"]:
        adapter_id = observation["adapter_id"]
        if adapter_id in seen:
            failures.append(f"adapter obrigatório duplicado: {adapter_id}")
            continue
        seen.add(adapter_id)
        canonical = manifests.get(adapter_id)
        if canonical is None:
            failures.append(f"adapter obrigatório não existe no registry canônico: {adapter_id}")
            continue
        _, manifest = canonical
        if observation["adapter_version"] != manifest["version"]:
            failures.append(
                f"{adapter_id}: adapter_version {observation['adapter_version']} diverge da versão canônica {manifest['version']}"
            )
        if manifest["constitution_version"] != policy["constitution_version"]:
            failures.append(f"{adapter_id}: manifesto não corresponde à versão constitucional da policy")

    return (policy if not failures else None), failures


def load_observation_policy(config_path: Path, project_root: Path) -> dict:
    policy, failures = validate_observation_policy(config_path, project_root)
    if failures or policy is None:
        raise ValueError("observation policy inválida: " + "; ".join(failures))
    return policy


def resolve_required_manifests(policy: dict) -> list[Path]:
    manifests = canonical_manifests_by_id()
    resolved: list[Path] = []
    for item in policy["required_observations"]:
        resolved.append(manifests[item["adapter_id"]][0])
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    try:
        _, failures = validate_observation_policy(args.config, args.project_root, args.schema)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Falha ao validar observation policy: {exc}", file=sys.stderr)
        return 1
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("OK: observation policy válida e vinculada a adapters canônicos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
