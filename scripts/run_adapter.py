#!/usr/bin/env python3
"""Executa somente adapters internos registrados sobre requests brokerados."""

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
from jsonschema import Draft202012Validator

from evolutive.adapters.registry import REGISTRY

if __package__:
    from .validate_adapter_contract import REQUEST_SCHEMA, RESULT_SCHEMA, validate_manifest
else:
    from validate_adapter_contract import REQUEST_SCHEMA, RESULT_SCHEMA, validate_manifest


def schema_errors(schema_path: Path, instance: dict) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return [error.message for error in Draft202012Validator(schema).iter_errors(instance)]


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def execute_adapter(manifest_path: Path, request: dict) -> dict:
    failures = validate_manifest(manifest_path)
    if failures:
        raise ValueError("manifesto inválido: " + "; ".join(failures))
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    request_failures = schema_errors(REQUEST_SCHEMA, request)
    if request_failures:
        raise ValueError("requisição inválida: " + "; ".join(request_failures))
    if request["adapter_id"] != manifest["id"]:
        raise ValueError("adapter_id não corresponde ao manifesto")
    if request["constitution_version"] != manifest["constitution_version"]:
        raise ValueError("request usa versão constitucional não autorizada pelo adapter")

    capabilities = manifest["capabilities"]
    accepted = set(capabilities["file_extensions"])
    for item in request["files"]:
        if Path(item["path"]).suffix not in accepted:
            raise ValueError(f"extensão não autorizada: {item['path']}")
        data = item["text"].encode("utf-8")
        if len(data) != item["size_bytes"]:
            raise ValueError(f"tamanho inconsistente: {item['path']}")
        if len(data) > capabilities["max_file_bytes"]:
            raise ValueError(f"arquivo excede capacidade declarada: {item['path']}")
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"checksum inconsistente: {item['path']}")

    entrypoint = manifest["runtime"]["entrypoint"]
    registered = REGISTRY.get(entrypoint)
    if registered is None:
        raise ValueError("entrypoint não pertence ao registro interno")
    actual = hashlib.sha256(canonical_bytes(registered["path"])).hexdigest()
    expected = manifest["runtime"]["implementation_sha256"]
    if actual != expected:
        raise ValueError(f"checksum da implementação diverge do manifesto: actual={actual}")

    result = registered["implementation"](request)
    result_failures = schema_errors(RESULT_SCHEMA, result)
    if result_failures:
        raise ValueError("resultado inválido: " + "; ".join(result_failures))
    if result["adapter_id"] != manifest["id"]:
        raise ValueError("resultado pertence a outro adapter")
    if result["adapter_version"] != manifest["version"]:
        raise ValueError("versão do resultado não corresponde ao manifesto")
    if result["ecosystem"] != manifest["ecosystem"]:
        raise ValueError("ecossistema do resultado diverge do manifesto")
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
        result = execute_adapter(args.manifest, request)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Falha ao executar adapter: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
