#!/usr/bin/env python3
"""Valida a política arquitetural declarada pelo consumidor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schema" / "architecture-policy.schema.json"
POLICY_RELATIVE_PATH = PurePosixPath(".evolutive/architecture-policy.yaml")


def schema_location(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "<raiz>"


def is_within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def literal_glob_prefix(pattern: str) -> str:
    positions = [index for token in ("*", "?", "[") if (index := pattern.find(token)) >= 0]
    if not positions:
        return pattern
    return pattern[: min(positions)].rstrip("/")


def confined_directory(project_root: Path, relative: str) -> bool:
    candidate = project_root / relative
    if candidate.is_symlink() or not candidate.is_dir():
        return False
    try:
        candidate.resolve().relative_to(project_root)
    except ValueError:
        return False
    return True


def validate_components(components: list[dict], authorized_roots: list[str], project_root: Path) -> list[str]:
    failures: list[str] = []
    by_id: dict[str, dict] = {}
    roots: list[tuple[str, str]] = []

    for component in components:
        component_id = component["id"]
        if component_id in by_id:
            failures.append(f"component id duplicado: {component_id}")
        by_id[component_id] = component

        for root in component["roots"]:
            if root == ".evolutive" or root.startswith(".evolutive/"):
                failures.append(f"{component_id}: raiz não pode usar .evolutive")
            if not any(is_within(root, allowed) for allowed in authorized_roots):
                failures.append(f"{component_id}: raiz {root} está fora do escopo autorizado")
            if not confined_directory(project_root, root):
                failures.append(f"{component_id}: raiz {root} deve existir como diretório regular dentro do projeto")
            roots.append((component_id, root))

        for pattern in component["public_surface"]:
            prefix = literal_glob_prefix(pattern)
            if not prefix or not any(is_within(prefix, root) for root in component["roots"]):
                failures.append(f"{component_id}: public_surface {pattern} deve permanecer nas raízes do componente")

    for index, (left_id, left_root) in enumerate(roots):
        for right_id, right_root in roots[index + 1 :]:
            if left_id == right_id:
                continue
            if is_within(left_root, right_root) or is_within(right_root, left_root):
                failures.append(f"raízes de componentes se sobrepõem: {left_id}:{left_root} e {right_id}:{right_root}")

    known = set(by_id)
    for component in components:
        for target in component["may_depend_on"]:
            if target == component["id"]:
                failures.append(f"{component['id']}: may_depend_on não deve listar o próprio componente")
            elif target not in known:
                failures.append(f"{component['id']}: may_depend_on referencia componente inexistente: {target}")

    return failures


def validate_architecture_policy(config_path: Path, project_root: Path, schema_path: Path = DEFAULT_SCHEMA) -> tuple[dict | None, list[str]]:
    project_root = project_root.resolve()
    evolutive = project_root / ".evolutive"
    policy_path = project_root / POLICY_RELATIVE_PATH.as_posix()
    if evolutive.is_symlink():
        return None, [".evolutive não pode ser link simbólico"]
    if not policy_path.exists():
        return None, ["architecture-policy.yaml ausente"]
    if policy_path.is_symlink():
        return None, ["architecture-policy.yaml não pode ser link simbólico"]
    try:
        policy_path.resolve().relative_to(project_root)
    except ValueError:
        return None, ["architecture-policy.yaml escapou da raiz do projeto"]

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    try:
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, [f"YAML inválido: {exc}"]

    errors = sorted(Draft202012Validator(schema).iter_errors(policy), key=lambda item: [str(part) for part in item.absolute_path])
    failures = [f"{schema_location(error)}: {error.message}" for error in errors]
    if errors or not isinstance(policy, dict):
        return None, failures

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if policy["constitution_version"] != config["constitution"]["version"]:
        failures.append("constitution_version diverge da versão constitucional do consumidor")
    failures.extend(validate_components(policy["components"], list(config["scope"]["roots"]), project_root))
    return (policy if not failures else None), failures


def load_architecture_policy(config_path: Path, project_root: Path) -> dict:
    policy, failures = validate_architecture_policy(config_path, project_root)
    if failures or policy is None:
        raise ValueError("política arquitetural inválida: " + "; ".join(failures))
    return policy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    try:
        _, failures = validate_architecture_policy(args.config, args.project_root, args.schema)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Falha ao validar política arquitetural: {exc}", file=sys.stderr)
        return 1
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("OK: política arquitetural válida e confinada ao escopo autorizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
