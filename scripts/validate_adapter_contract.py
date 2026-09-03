#!/usr/bin/env python3
"""Valida manifesto, request, result e implementação fixada dos adapters."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = ROOT / "schema" / "adapter-manifest.schema.json"
REQUEST_SCHEMA = ROOT / "schema" / "adapter-request.schema.json"
RESULT_SCHEMA = ROOT / "schema" / "adapter-result.schema.json"
MANIFEST_TEMPLATE = ROOT / "adapters" / "python-imports.yaml"
IMPLEMENTATIONS = {
    "evolutive.adapters.python_imports:adapt": ROOT / "evolutive" / "adapters" / "python_imports.py",
}


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def schema_failures(path: Path, instance: dict) -> list[str]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return [error.message for error in Draft202012Validator(schema).iter_errors(instance)]


def validate_manifest(path: Path = MANIFEST_TEMPLATE) -> list[str]:
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    failures = schema_failures(MANIFEST_SCHEMA, manifest)
    if not isinstance(manifest, dict):
        return failures + ["manifesto deve ser objeto"]
    if failures:
        return failures

    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    if manifest["constitution_version"] != version:
        failures.append("constitution_version do adapter diverge da Constituição")

    entrypoint = manifest["runtime"]["entrypoint"]
    implementation = IMPLEMENTATIONS.get(entrypoint)
    if implementation is None:
        failures.append("entrypoint não pertence ao registro interno de adapters")
    else:
        actual = hashlib.sha256(canonical_bytes(implementation)).hexdigest()
        expected = manifest["runtime"]["implementation_sha256"]
        if actual != expected:
            failures.append(f"implementation_sha256 diverge: actual={actual}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_TEMPLATE)
    args = parser.parse_args()
    try:
        for schema in (MANIFEST_SCHEMA, REQUEST_SCHEMA, RESULT_SCHEMA):
            loaded = json.loads(schema.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(loaded)
        failures = validate_manifest(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Falha ao validar adapter: {exc}", file=sys.stderr)
        return 1
    if failures:
        print("Contrato de adapter inválido:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("OK: schemas, manifesto, entrypoint e checksum do adapter estão consistentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
