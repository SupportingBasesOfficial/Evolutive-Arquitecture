#!/usr/bin/env python3
"""Valida e normaliza evidência arquitetural portável de um consumidor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schema" / "architecture-evidence.schema.json"
EVIDENCE_RELATIVE_PATH = PurePosixPath(".evolutive/architecture-evidence.yaml")


def schema_location(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "<raiz>"


def is_safe_relative(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and value != "."


def is_within_declared_root(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def literal_glob_prefix(pattern: str) -> str:
    wildcard_positions = [
        index for token in ("*", "?", "[") if (index := pattern.find(token)) >= 0
    ]
    if not wildcard_positions:
        return pattern
    prefix = pattern[: min(wildcard_positions)]
    return prefix.rstrip("/")


def path_is_regular_and_confined(project_root: Path, relative: str) -> bool:
    candidate = project_root / relative
    if candidate.is_symlink() or not candidate.is_file():
        return False
    try:
        candidate.resolve().relative_to(project_root)
    except ValueError:
        return False
    return True


def root_is_directory_and_confined(project_root: Path, relative: str) -> bool:
    candidate = project_root / relative
    if candidate.is_symlink() or not candidate.is_dir():
        return False
    try:
        candidate.resolve().relative_to(project_root)
    except ValueError:
        return False
    return True


def load_project_config(config_path: Path) -> dict:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("configuração do consumidor deve ser um objeto")
    return data


def validate_architecture_evidence(
    config_path: Path,
    project_root: Path,
    schema_path: Path = DEFAULT_SCHEMA,
) -> tuple[dict | None, list[str]]:
    project_root = project_root.resolve()
    evidence_path = project_root / EVIDENCE_RELATIVE_PATH.as_posix()
    failures: list[str] = []

    evolutive_dir = project_root / ".evolutive"
    if evolutive_dir.is_symlink():
        return None, [".evolutive não pode ser link simbólico"]
    if not evidence_path.exists():
        return None, []
    if evidence_path.is_symlink():
        return None, ["architecture-evidence.yaml não pode ser link simbólico"]

    try:
        evidence_path.resolve().relative_to(project_root)
    except ValueError:
        return None, ["architecture-evidence.yaml escapou da raiz do projeto"]

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    try:
        evidence = yaml.safe_load(evidence_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, [f"YAML inválido: {exc}"]

    validator = Draft202012Validator(schema)
    schema_errors = sorted(
        validator.iter_errors(evidence),
        key=lambda item: [str(part) for part in item.absolute_path],
    )
    failures.extend(
        f"{schema_location(error)}: {error.message}" for error in schema_errors
    )
    if schema_errors or not isinstance(evidence, dict):
        return None, failures

    config = load_project_config(config_path)
    expected_version = config["constitution"]["version"]
    if evidence["constitution_version"] != expected_version:
        failures.append(
            "constitution_version diverge da versão constitucional do consumidor"
        )

    authorized_roots = list(config["scope"]["roots"])
    components = evidence["graph"]["components"]
    component_by_id: dict[str, dict] = {}
    root_owners: list[tuple[str, str]] = []

    for component in components:
        component_id = component["id"]
        if component_id in component_by_id:
            failures.append(f"component id duplicado: {component_id}")
        component_by_id[component_id] = component

        for root in component["roots"]:
            if not is_safe_relative(root):
                failures.append(f"{component_id}: raiz inválida: {root}")
                continue
            if root == ".evolutive" or root.startswith(".evolutive/"):
                failures.append(f"{component_id}: raiz não pode usar .evolutive")
            if not any(is_within_declared_root(root, item) for item in authorized_roots):
                failures.append(
                    f"{component_id}: raiz {root} está fora do escopo autorizado"
                )
            if not root_is_directory_and_confined(project_root, root):
                failures.append(
                    f"{component_id}: raiz {root} deve existir como diretório regular dentro do projeto"
                )
            root_owners.append((component_id, root))

        for pattern in component["public_surface"]:
            if not is_safe_relative(pattern):
                failures.append(f"{component_id}: public_surface inválida: {pattern}")
                continue
            prefix = literal_glob_prefix(pattern)
            if not prefix or not any(
                is_within_declared_root(prefix, root) for root in component["roots"]
            ):
                failures.append(
                    f"{component_id}: public_surface {pattern} deve permanecer nas raízes do componente"
                )

    for index, (first_id, first_root) in enumerate(root_owners):
        for second_id, second_root in root_owners[index + 1 :]:
            if first_id == second_id:
                continue
            if is_within_declared_root(first_root, second_root) or is_within_declared_root(
                second_root, first_root
            ):
                failures.append(
                    f"raízes de componentes se sobrepõem: {first_id}:{first_root} e {second_id}:{second_root}"
                )

    known_ids = set(component_by_id)
    for component in components:
        component_id = component["id"]
        for target in component["may_depend_on"]:
            if target == component_id:
                failures.append(f"{component_id}: may_depend_on não deve listar o próprio componente")
            elif target not in known_ids:
                failures.append(f"{component_id}: may_depend_on referencia componente inexistente: {target}")

    seen_dependencies: set[tuple[str, str, str, str, str]] = set()
    for dependency in evidence["graph"]["dependencies"]:
        source_id = dependency["source_component"]
        target_id = dependency["target_component"]
        source = component_by_id.get(source_id)
        target = component_by_id.get(target_id)
        if source is None:
            failures.append(f"dependência referencia source_component inexistente: {source_id}")
            continue
        if target is None:
            failures.append(f"dependência referencia target_component inexistente: {target_id}")
            continue

        source_path = dependency["source_path"]
        target_path = dependency["target_path"]
        if not any(is_within_declared_root(source_path, root) for root in source["roots"]):
            failures.append(
                f"dependência {source_id}->{target_id}: source_path fora das raízes de {source_id}"
            )
        if not any(is_within_declared_root(target_path, root) for root in target["roots"]):
            failures.append(
                f"dependência {source_id}->{target_id}: target_path fora das raízes de {target_id}"
            )
        if not path_is_regular_and_confined(project_root, source_path):
            failures.append(
                f"dependência {source_id}->{target_id}: source_path deve ser arquivo regular existente"
            )
        if not path_is_regular_and_confined(project_root, target_path):
            failures.append(
                f"dependência {source_id}->{target_id}: target_path deve ser arquivo regular existente"
            )

        identity = (
            source_id,
            target_id,
            source_path,
            target_path,
            dependency["kind"],
        )
        if identity in seen_dependencies:
            failures.append(
                f"dependência duplicada: {source_id}->{target_id} {source_path} -> {target_path}"
            )
        seen_dependencies.add(identity)

    return evidence if not failures else None, failures


def load_architecture_graph(config_path: Path, project_root: Path) -> dict | None:
    evidence, failures = validate_architecture_evidence(config_path, project_root)
    if failures:
        raise ValueError("evidência arquitetural inválida: " + "; ".join(failures))
    if evidence is None:
        return None
    return evidence["graph"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        _, failures = validate_architecture_evidence(
            args.config,
            args.project_root,
            args.schema,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Falha ao validar evidência arquitetural: {exc}", file=sys.stderr)
        return 1

    if failures:
        print("Evidência arquitetural inválida:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("OK: evidência arquitetural ausente ou válida e confinada ao escopo autorizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
