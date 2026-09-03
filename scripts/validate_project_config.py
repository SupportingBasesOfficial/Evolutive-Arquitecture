#!/usr/bin/env python3
"""Valida apenas o contrato .evolutive/config.yaml de um consumidor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator, FormatChecker

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = REPOSITORY_ROOT / "schema" / "project-config.schema.json"
DEFAULT_CONFIG = REPOSITORY_ROOT / "templates" / "project-config.yaml"
EXPECTED_RELEASE_PREFIX = (
    "https://github.com/SupportingBasesOfficial/Evolutive-Arquitecture/"
    "releases/download"
)


def schema_location(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "<raiz>"


def safe_relative_path(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and value != "."


def validate_config(config_path: Path, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"YAML inválido: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    failures = [
        f"{schema_location(error)}: {error.message}"
        for error in sorted(
            validator.iter_errors(config),
            key=lambda item: [str(part) for part in item.absolute_path],
        )
    ]
    if failures or not isinstance(config, dict):
        return failures

    constitution = config["constitution"]
    version = constitution["version"]
    expected_url = (
        f"{EXPECTED_RELEASE_PREFIX}/v{version}/"
        f"evolutive-architecture-{version}.zip"
    )
    if constitution["artifact_url"] != expected_url:
        failures.append(
            "constitution.artifact_url: deve apontar exatamente para o bundle "
            "oficial da versão declarada."
        )

    for index, value in enumerate(config["scope"]["roots"]):
        if not safe_relative_path(value):
            failures.append(
                f"scope.roots.{index}: use uma raiz relativa específica, sem '..' "
                "e diferente de '.'."
            )
        if value == ".evolutive" or value.startswith(".evolutive/"):
            failures.append(
                f"scope.roots.{index}: a configuração não pode analisar a si mesma."
            )

    for index, value in enumerate(config["scope"]["exclude"]):
        if value.startswith("/") or "\\" in value or ".." in PurePosixPath(value).parts:
            failures.append(
                f"scope.exclude.{index}: a exclusão deve ser relativa e não pode conter '..'."
            )

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", nargs="?", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures = validate_config(args.config, args.schema)
    if failures:
        print("Configuração inválida:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"OK: contrato do consumidor válido em {args.config}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
