#!/usr/bin/env python3
"""Executa somente verificadores internos registrados, sem expor a raiz."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from evolutive.checkers.architecture import check as architecture_check

if __package__:
    from .validate_checker_contract import (
        MANIFEST_SCHEMA,
        REQUEST_SCHEMA,
        RESULT_SCHEMA,
        validate_manifest,
    )
else:
    from validate_checker_contract import (
        MANIFEST_SCHEMA,
        REQUEST_SCHEMA,
        RESULT_SCHEMA,
        validate_manifest,
    )


REGISTRY = {
    "evolutive.checkers.architecture:check": (
        architecture_check,
        REPOSITORY_ROOT / "evolutive" / "checkers" / "architecture.py",
    ),
}


def schema_errors(schema_path: Path, instance: dict) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [error.message for error in validator.iter_errors(instance)]


def canonical_implementation_bytes(path: Path) -> bytes:
    """Retorna a representação LF usada para fixar código-fonte de checker."""
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def execute_checker(manifest_path: Path, request: dict) -> dict:
    failures = validate_manifest(manifest_path)
    if failures:
        raise ValueError("manifesto inválido: " + "; ".join(failures))

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    request_failures = schema_errors(REQUEST_SCHEMA, request)
    if request_failures:
        raise ValueError("requisição inválida: " + "; ".join(request_failures))

    if request["checker_id"] != manifest["id"]:
        raise ValueError("checker_id não corresponde ao manifesto")
    if not set(request["rule_ids"]).issubset(set(manifest["rules"])):
        raise ValueError("requisição contém regra não concedida ao verificador")

    capabilities = manifest["capabilities"]
    for item in request["files"]:
        if item["size_bytes"] > capabilities["max_file_bytes"]:
            raise ValueError(f"arquivo excede capacidade declarada: {item['path']}")
        if capabilities["content_access"] == "none" and "text" in item:
            raise ValueError(f"conteúdo não autorizado: {item['path']}")
        if "text" in item:
            data = item["text"].encode("utf-8")
            if len(data) != item["size_bytes"]:
                raise ValueError(f"tamanho inconsistente: {item['path']}")
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError(f"checksum inconsistente: {item['path']}")

    entrypoint = manifest["runtime"]["entrypoint"]
    registered = REGISTRY.get(entrypoint)
    if registered is None:
        raise ValueError("entrypoint não pertence ao registro interno")

    implementation, implementation_path = registered
    actual_digest = hashlib.sha256(
        canonical_implementation_bytes(implementation_path)
    ).hexdigest()
    if actual_digest != manifest["runtime"]["implementation_sha256"]:
        raise ValueError("checksum da implementação diverge do manifesto")

    result = implementation(request)
    result_failures = schema_errors(RESULT_SCHEMA, result)
    if result_failures:
        raise ValueError("resultado inválido: " + "; ".join(result_failures))

    if result["checker_id"] != manifest["id"]:
        raise ValueError("resultado pertence a outro verificador")
    if result["checker_version"] != manifest["version"]:
        raise ValueError("versão do resultado não corresponde ao manifesto")

    outcome_ids = [item["rule_id"] for item in result["outcomes"]]
    if len(outcome_ids) != len(set(outcome_ids)):
        raise ValueError("resultado contém regras duplicadas")
    if set(outcome_ids) != set(request["rule_ids"]):
        raise ValueError("resultado não cobre exatamente as regras solicitadas")

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        result = execute_checker(args.manifest, request)
    except (OSError, ValueError, json.JSONDecodeError, KeyError) as exc:
        print(f"Falha ao executar verificador: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
