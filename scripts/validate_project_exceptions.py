#!/usr/bin/env python3
"""Valida exceções do consumidor contra a Constituição verificada."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schema" / "project-exception.schema.json"

if __package__:
    from .plan_compliance import load_verified_bundle
    from .validate_project_config import DEFAULT_SCHEMA as PROJECT_CONFIG_SCHEMA
    from .validate_project_config import validate_config
else:
    from plan_compliance import load_verified_bundle
    from validate_project_config import DEFAULT_SCHEMA as PROJECT_CONFIG_SCHEMA
    from validate_project_config import validate_config


def location(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "<raiz>"


def canonical_relative_path(value: str) -> PurePosixPath:
    if "\\" in value:
        raise ValueError("caminhos devem usar '/' como separador")
    parts = value.split("/")
    if not value or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("caminho deve ser relativo, normalizado e sem segmentos vazios, '.' ou '..'")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ValueError("caminho absoluto não é permitido")
    if path.parts[0] == ".evolutive":
        raise ValueError("escopo de exceção não pode apontar para .evolutive/")
    return path


def is_within_authorized_root(path: PurePosixPath, roots: list[PurePosixPath]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def resolve_exception_directory(project_root: Path) -> tuple[Path | None, list[str]]:
    """Resolve o ledger sem permitir que .evolutive redirecione para fora do projeto."""
    project = project_root.resolve()
    evolutive = project / ".evolutive"
    if not evolutive.exists():
        return None, []
    if evolutive.is_symlink():
        return None, [f"{evolutive}: .evolutive não pode ser link simbólico."]
    if not evolutive.is_dir():
        return None, [f"{evolutive}: .evolutive deve ser um diretório."]

    exceptions = evolutive / "exceptions"
    if not exceptions.exists():
        return None, []
    if exceptions.is_symlink():
        return None, [f"{exceptions}: diretório de exceções não pode ser link simbólico."]

    resolved = exceptions.resolve()
    try:
        resolved.relative_to(project)
    except ValueError:
        return None, [f"{exceptions}: diretório de exceções escapa da árvore do consumidor."]
    return resolved, []


def validate_exception_records(
    exceptions_dir: Path,
    rules: list[dict],
    constitution_version: str,
    authorized_roots: list[str],
    schema_path: Path = DEFAULT_SCHEMA,
) -> list[str]:
    """Valida somente o diretório explícito de exceções do consumidor."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    try:
        roots = [canonical_relative_path(value) for value in authorized_roots]
    except ValueError as exc:
        return [f"scope.roots inválido: {exc}"]

    if not exceptions_dir.exists():
        return []
    if exceptions_dir.is_symlink():
        return [f"{exceptions_dir}: diretório de exceções não pode ser link simbólico."]
    if not exceptions_dir.is_dir():
        return [f"{exceptions_dir}: caminho de exceções deve ser um diretório."]

    failures: list[str] = []
    rules_by_id = {
        rule["id"]: rule
        for rule in rules
        if isinstance(rule, dict) and isinstance(rule.get("id"), str)
    }
    seen_ids: dict[str, Path] = {}

    for path in sorted(exceptions_dir.iterdir(), key=lambda item: item.name):
        if path.is_symlink():
            failures.append(f"{path}: registros de exceção não podem ser links simbólicos.")
            continue
        if not path.is_file() or path.suffix != ".yaml":
            failures.append(f"{path}: somente arquivos YAML regulares são permitidos.")
            continue

        try:
            record = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            failures.append(f"{path}: YAML inválido: {exc}")
            continue

        if not isinstance(record, dict):
            failures.append(f"{path}: a raiz deve ser um objeto.")
            continue

        schema_errors = sorted(
            validator.iter_errors(record),
            key=lambda item: [str(part) for part in item.absolute_path],
        )
        for error in schema_errors:
            failures.append(f"{path}:{location(error)}: {error.message}")
        if schema_errors:
            continue

        exception_id = record["exception_id"]
        if path.name != f"{exception_id}.yaml":
            failures.append(f"{path}: o arquivo deve se chamar {exception_id}.yaml.")
        if exception_id in seen_ids:
            failures.append(
                f"{path}: exception_id duplicado; já declarado em {seen_ids[exception_id]}."
            )
        else:
            seen_ids[exception_id] = path

        if record["constitution_version"] != constitution_version:
            failures.append(
                f"{path}: constitution_version deve ser {constitution_version}."
            )

        rule = rules_by_id.get(record["rule_id"])
        if rule is None:
            failures.append(f"{path}: rule_id {record['rule_id']} não existe no bundle.")
            continue

        expires_on = record["validity"]["expires_on"]
        review_condition = record["validity"]["review_condition"]
        if expires_on is None and review_condition is None:
            failures.append(
                f"{path}: exceção deve possuir expires_on ou review_condition."
            )
        if expires_on is not None:
            if date.fromisoformat(expires_on) < date.fromisoformat(record["decision"]["decided_at"]):
                failures.append(
                    f"{path}: expires_on não pode ser anterior a decision.decided_at."
                )

        for declared in record["scope"]["paths"]:
            try:
                relative = canonical_relative_path(declared)
            except ValueError as exc:
                failures.append(f"{path}: scope.paths contém '{declared}' inválido: {exc}.")
                continue
            if not is_within_authorized_root(relative, roots):
                failures.append(
                    f"{path}: scope '{declared}' está fora das raízes autorizadas."
                )

        if record["decision"]["outcome"] == "approved":
            exceptions = rule.get("exceptions", {})
            if exceptions.get("allowed") is not True:
                failures.append(
                    f"{path}: {record['rule_id']} não permite exceções aprovadas."
                )
            if rule.get("status") not in {"active", "deprecated"}:
                failures.append(
                    f"{path}: exceção aprovada exige regra active ou deprecated; "
                    f"estado atual é {rule.get('status')}."
                )

    return failures


def validate_project_exceptions(
    config_path: Path,
    project_root: Path,
    bundle_path: Path,
    schema_path: Path = DEFAULT_SCHEMA,
) -> list[str]:
    """Verifica fonte/configuração e valida o ledger fixo .evolutive/exceptions/."""
    config_failures = validate_config(config_path, PROJECT_CONFIG_SCHEMA)
    if config_failures:
        return ["configuração inválida: " + "; ".join(config_failures)]

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    source = load_verified_bundle(
        bundle_path,
        config["constitution"]["sha256"],
        config["constitution"]["version"],
    )
    exceptions_dir, location_failures = resolve_exception_directory(project_root)
    if location_failures:
        return location_failures
    if exceptions_dir is None:
        return []

    return validate_exception_records(
        exceptions_dir,
        source["rules"],
        config["constitution"]["version"],
        config["scope"]["roots"],
        schema_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        failures = validate_project_exceptions(
            args.config,
            args.project_root,
            args.bundle,
            args.schema,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Falha ao validar exceções: {exc}", file=sys.stderr)
        return 1

    if failures:
        print("Falha na validação das exceções do consumidor:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("OK: registros de exceção do consumidor são auditáveis e limitados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
