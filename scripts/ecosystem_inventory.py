#!/usr/bin/env python3
"""Descobre superfícies de código conhecidas no inventário autorizado sem ler conteúdo."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

if __package__:
    from .adapter_broker import canonical_sha256
    from .run_adapter import canonical_bytes
    from .scope_broker import build_inventory
    from .validate_adapter_contract import CANONICAL_MANIFESTS, validate_manifest
else:
    from adapter_broker import canonical_sha256
    from run_adapter import canonical_bytes
    from scope_broker import build_inventory
    from validate_adapter_contract import CANONICAL_MANIFESTS, validate_manifest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "governance" / "ecosystem-catalog.yaml"
CATALOG_SCHEMA = ROOT / "schema" / "ecosystem-catalog.schema.json"
INVENTORY_SCHEMA = ROOT / "schema" / "ecosystem-inventory.schema.json"
DISCOVERER_MANIFEST = ROOT / "governance" / "ecosystem-discoverer.yaml"
DISCOVERER_MANIFEST_SCHEMA = ROOT / "schema" / "ecosystem-discoverer-manifest.schema.json"
DISCOVERER_ID = "evolutive.ecosystem.discoverer"
DISCOVERER_VERSION = "0.1.0"


def schema_failures(schema_path: Path, value: object) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(value))


def canonical_adapters_by_id() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in sorted(CANONICAL_MANIFESTS.glob("*.yaml")):
        failures = validate_manifest(path)
        if failures:
            raise ValueError(f"manifesto canônico inválido {path.name}: " + "; ".join(failures))
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        if manifest["id"] in result:
            raise ValueError(f"adapter canônico duplicado: {manifest['id']}")
        result[manifest["id"]] = manifest
    return result


def load_catalog() -> dict:
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    failures = schema_failures(CATALOG_SCHEMA, catalog)
    if failures:
        raise ValueError("catálogo de ecossistemas inválido: " + "; ".join(failures))
    constitution_version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    if catalog["constitution_version"] != constitution_version:
        raise ValueError("constitution_version do catálogo diverge da Constituição")

    adapters = canonical_adapters_by_id()
    ids: set[str] = set()
    extensions: dict[str, str] = {}
    for surface in catalog["surfaces"]:
        surface_id = surface["id"]
        if surface_id in ids:
            raise ValueError(f"surface id duplicado no catálogo: {surface_id}")
        ids.add(surface_id)
        for extension in surface["extensions"]:
            if extension in extensions:
                raise ValueError(
                    f"extensão {extension} aparece em múltiplas superfícies: {extensions[extension]} e {surface_id}"
                )
            extensions[extension] = surface_id

        observation = surface["observation"]
        if observation is None:
            continue
        manifest = adapters.get(observation["adapter_id"])
        if manifest is None:
            raise ValueError(f"catálogo referencia adapter inexistente: {observation['adapter_id']}")
        if manifest["version"] != observation["adapter_version"]:
            raise ValueError(f"versão do adapter diverge no catálogo: {observation['adapter_id']}")
        if manifest["ecosystem"] != surface["ecosystem"]:
            raise ValueError(f"ecossistema diverge entre catálogo e adapter: {observation['adapter_id']}")
        supported = set(manifest["capabilities"]["file_extensions"])
        missing = sorted(set(surface["extensions"]) - supported)
        if missing:
            raise ValueError(
                f"catálogo atribui extensões não suportadas ao adapter {observation['adapter_id']}: {missing}"
            )
    return catalog


def validate_discoverer_authority() -> dict:
    manifest = yaml.safe_load(DISCOVERER_MANIFEST.read_text(encoding="utf-8"))
    failures = schema_failures(DISCOVERER_MANIFEST_SCHEMA, manifest)
    if failures:
        raise ValueError("manifesto do ecosystem discoverer inválido: " + "; ".join(failures))
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    if manifest["constitution_version"] != version:
        raise ValueError("constitution_version do discoverer diverge da Constituição")
    if manifest["id"] != DISCOVERER_ID or manifest["version"] != DISCOVERER_VERSION:
        raise ValueError("identidade do ecosystem discoverer diverge da implementação")
    actual = hashlib.sha256(canonical_bytes(Path(__file__))).hexdigest()
    if manifest["implementation_sha256"] != actual:
        raise ValueError(f"implementation_sha256 do ecosystem discoverer diverge: actual={actual}")
    return manifest


def discover_ecosystems(config_path: Path, project_root: Path) -> dict:
    discoverer = validate_discoverer_authority()
    catalog = load_catalog()
    inventory = build_inventory(config_path, project_root)

    by_extension: dict[str, dict] = {}
    for surface in catalog["surfaces"]:
        for extension in surface["extensions"]:
            by_extension[extension] = surface

    paths_by_surface: dict[str, list[str]] = {}
    extensions_by_surface: dict[str, set[str]] = {}
    surface_by_id = {item["id"]: item for item in catalog["surfaces"]}
    unclassified_extensions: set[str] = set()
    unclassified_count = 0

    for item in inventory["files"]:
        suffix = Path(item["path"]).suffix
        surface = by_extension.get(suffix)
        if surface is None:
            unclassified_count += 1
            unclassified_extensions.add(suffix or "<none>")
            continue
        surface_id = surface["id"]
        paths_by_surface.setdefault(surface_id, []).append(item["path"])
        extensions_by_surface.setdefault(surface_id, set()).add(suffix)

    detected: list[dict] = []
    for surface_id in sorted(paths_by_surface):
        surface = surface_by_id[surface_id]
        paths = sorted(paths_by_surface[surface_id])
        detected.append({
            "surface_id": surface_id,
            "ecosystem": surface["ecosystem"],
            "extensions_detected": sorted(extensions_by_surface[surface_id]),
            "files_count": len(paths),
            "paths_sha256": canonical_sha256(paths),
            "observation": surface["observation"],
        })

    result = {
        "inventory_version": 1,
        "constitution_version": catalog["constitution_version"],
        "subject": {
            "inventory_sha256": canonical_sha256(inventory),
            "catalog_sha256": canonical_sha256(catalog),
        },
        "scope": {
            "basis": "governed_ecosystem_catalog",
            "catalog_scope_only": True,
        },
        "evaluator": {
            "id": discoverer["id"],
            "version": discoverer["version"],
            "implementation_sha256": discoverer["implementation_sha256"],
        },
        "detected_surfaces": detected,
        "unclassified_files": {
            "count": unclassified_count,
            "extensions": sorted(unclassified_extensions),
        },
    }
    failures = schema_failures(INVENTORY_SCHEMA, result)
    if failures:
        raise ValueError("ecosystem inventory gerado é inválido: " + "; ".join(failures))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = discover_ecosystems(args.config, args.project_root)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(f"Falha no ecosystem inventory: {exc}", file=sys.stderr)
        return 1
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
