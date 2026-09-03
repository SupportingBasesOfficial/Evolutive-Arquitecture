#!/usr/bin/env python3
"""Valida schemas, manifestos e implementações fixadas dos adapters."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml
from jsonschema import Draft202012Validator

from evolutive.adapters.registry import REGISTRY

MANIFEST_SCHEMA = ROOT / "schema" / "adapter-manifest.schema.json"
REQUEST_SCHEMA = ROOT / "schema" / "adapter-request.schema.json"
RESULT_SCHEMA = ROOT / "schema" / "adapter-result.schema.json"
CANONICAL_MANIFESTS = ROOT / "adapters"
MANIFEST_TEMPLATE = CANONICAL_MANIFESTS / "python-imports.yaml"


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
    registered = REGISTRY.get(entrypoint)
    if registered is None:
        failures.append("entrypoint não pertence ao registro interno de adapters")
    else:
        actual = hashlib.sha256(canonical_bytes(registered["path"])).hexdigest()
        expected = manifest["runtime"]["implementation_sha256"]
        if actual != expected:
            failures.append(f"implementation_sha256 diverge: actual={actual}")
    return failures


def validate_all_manifests() -> list[str]:
    manifests = sorted(CANONICAL_MANIFESTS.glob("*.yaml"))
    failures: list[str] = []
    if not manifests:
        return ["nenhum manifesto de adapter encontrado"]
    seen_ids: set[str] = set()
    seen_entrypoints: set[str] = set()
    for path in manifests:
        local = validate_manifest(path)
        failures.extend(f"{path.relative_to(ROOT).as_posix()}: {item}" for item in local)
        if local:
            continue
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        if manifest["id"] in seen_ids:
            failures.append(f"{path.relative_to(ROOT).as_posix()}: id de adapter duplicado")
        if manifest["runtime"]["entrypoint"] in seen_entrypoints:
            failures.append(f"{path.relative_to(ROOT).as_posix()}: entrypoint de adapter duplicado")
        seen_ids.add(manifest["id"])
        seen_entrypoints.add(manifest["runtime"]["entrypoint"])

    registered = set(REGISTRY)
    if seen_entrypoints != registered:
        missing = sorted(registered - seen_entrypoints)
        extra = sorted(seen_entrypoints - registered)
        if missing:
            failures.append("registry sem manifesto: " + ", ".join(missing))
        if extra:
            failures.append("manifesto sem registry: " + ", ".join(extra))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        for schema in (MANIFEST_SCHEMA, REQUEST_SCHEMA, RESULT_SCHEMA):
            loaded = json.loads(schema.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(loaded)
        failures = validate_manifest(args.manifest) if args.manifest else validate_all_manifests()
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Falha ao validar adapter: {exc}", file=sys.stderr)
        return 1
    if failures:
        print("Contrato de adapter inválido:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("OK: schemas, manifestos, registry e checksums dos adapters estão consistentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
