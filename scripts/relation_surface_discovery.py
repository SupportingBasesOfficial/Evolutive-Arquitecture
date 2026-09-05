#!/usr/bin/env python3
"""Descobre relation surfaces canônicas sem afirmar cobertura global do projeto."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator

from scripts.scope_broker import build_inventory

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "VERSION"
MANIFEST = ROOT / "governance" / "relation-surface-discoverer.yaml"
MANIFEST_SCHEMA = ROOT / "schema" / "relation-surface-discoverer-manifest.schema.json"
DESCRIPTOR_SCHEMA = ROOT / "schema" / "relation-surface-descriptor.schema.json"
RESULT_SCHEMA = ROOT / "schema" / "relation-surface-discovery-result.schema.json"
DECLARATION_SCHEMA = ROOT / "schema" / "relation-surface-inventory-declaration.schema.json"
IMPLEMENTATION = Path(__file__).resolve()
DISCOVERER_ID = "evolutive.semantic.relation_surface_discoverer"
DISCOVERER_VERSION = "0.1.0"
RELATION_ID = "ffi_native_linkage"
CANONICAL_SUFFIX = ".evolutive-linker-surface.json"
MAX_DESCRIPTOR_BYTES = 1_048_576
MAX_TARGET_BYTES = 1_048_576


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _implementation_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _schema_failures(schema_path: Path, value: object) -> list[str]:
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(value))


def _reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON contém membro duplicado: {key}")
        result[key] = value
    return result


def _normalize_identity(identity: str) -> str:
    if not isinstance(identity, str) or not identity or "\\" in identity:
        raise ValueError("identity deve ser path POSIX relativo")
    path = PurePosixPath(identity)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("identity inválida ou escapando do projeto")
    normalized = path.as_posix()
    if normalized != identity:
        raise ValueError("identity deve estar em forma POSIX canônica")
    return normalized


def validate_discoverer_authority() -> dict:
    manifest = _load_yaml(MANIFEST)
    failures = _schema_failures(MANIFEST_SCHEMA, manifest)
    if failures:
        raise ValueError("manifesto do relation surface discoverer inválido: " + "; ".join(failures))
    version = VERSION.read_text(encoding="ascii").strip()
    if manifest["constitution_version"] != version:
        raise ValueError("relation surface discoverer diverge de VERSION")
    if manifest["id"] != DISCOVERER_ID or manifest["version"] != DISCOVERER_VERSION:
        raise ValueError("identidade do relation surface discoverer diverge do canônico")
    if manifest["canonical_descriptor_suffix"] != CANONICAL_SUFFIX:
        raise ValueError("descriptor suffix do relation surface discoverer diverge do canônico")
    expected_authority = {
        "discovery_only": True,
        "may_assert_canonical_descriptor_discovery": True,
        "may_assert_surface_kind_authenticity": False,
        "may_assert_project_relation_coverage": False,
        "may_assert_complete_rule_semantics": False,
        "may_assert_rule_outcome": False,
        "may_change_rule_status": False,
    }
    if manifest["authority"] != expected_authority:
        raise ValueError("authority do relation surface discoverer diverge do fence canônico")
    actual = _implementation_sha256(IMPLEMENTATION)
    if manifest["implementation_sha256"] != actual:
        raise ValueError(
            "implementation_sha256 do relation surface discoverer diverge: "
            f"esperado {manifest['implementation_sha256']}, atual {actual}"
        )
    return manifest


def _confined_regular_file(project_root: Path, identity: str) -> Path:
    candidate = project_root / identity
    if candidate.is_symlink():
        raise ValueError(f"surface discovery encontrou symlink: {identity}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(project_root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"surface discovery detectou escape do project root: {identity}") from exc
    if not resolved.is_file():
        raise ValueError(f"surface discovery encontrou arquivo não regular: {identity}")
    return resolved


def _read_stable_file(project_root: Path, identity: str, expected_size: int, max_bytes: int) -> bytes:
    path = _confined_regular_file(project_root, identity)
    before = path.stat().st_size
    if before != expected_size:
        raise ValueError(f"surface discovery detectou snapshot drift: {identity}")
    if before > max_bytes:
        raise ValueError(f"surface discovery excedeu limite de tamanho: {identity}")
    content = path.read_bytes()
    after_resolved = _confined_regular_file(project_root, identity)
    if after_resolved != path:
        raise ValueError(f"surface discovery detectou path instável: {identity}")
    after = after_resolved.stat().st_size
    if after != before or len(content) != before:
        raise ValueError(f"surface discovery detectou arquivo instável: {identity}")
    return content


def _declared_targets(declaration: dict | None, version: str) -> set[tuple[str, str]]:
    if declaration is None:
        return set()
    failures = _schema_failures(DECLARATION_SCHEMA, declaration)
    if failures:
        raise ValueError("relation surface inventory declaration inválida: " + "; ".join(failures))
    if declaration["constitution_version"] != version or declaration["relation_id"] != RELATION_ID:
        raise ValueError("relation surface inventory declaration diverge do escopo canônico")
    seen_identities: set[str] = set()
    declared: set[tuple[str, str]] = set()
    for row in declaration["surfaces"]:
        identity = _normalize_identity(row["identity"])
        if identity in seen_identities:
            raise ValueError(f"relation surface inventory declaration contém identity duplicada: {identity}")
        seen_identities.add(identity)
        declared.add((identity, row["sha256"]))
    return declared


def _unique_inventory_files(files: list[dict]) -> list[dict]:
    unique: dict[str, dict] = {}
    for row in files:
        identity = _normalize_identity(row["path"])
        previous = unique.get(identity)
        if previous is None:
            unique[identity] = row
            continue
        if previous != row:
            raise ValueError(f"inventário contém bindings conflitantes para identity: {identity}")
    return [unique[key] for key in sorted(unique)]


def discover_relation_surfaces(
    config_path: Path,
    project_root: Path,
    declaration: dict | None = None,
) -> dict:
    manifest = validate_discoverer_authority()
    version = manifest["constitution_version"]
    inventory = build_inventory(config_path, project_root)
    project_root = project_root.resolve()
    inventory_files = _unique_inventory_files(inventory["files"])
    inventory_by_path = {row["path"]: row for row in inventory_files}
    declared = _declared_targets(declaration, version)

    inventory_complete = not inventory["missing_roots"] and not inventory["skipped_symlinks"]
    descriptors: list[dict] = []
    targets_by_identity: dict[str, dict] = {}

    for inventory_item in inventory_files:
        descriptor_identity = inventory_item["path"]
        if not descriptor_identity.endswith(CANONICAL_SUFFIX):
            continue
        descriptor_content = _read_stable_file(
            project_root,
            descriptor_identity,
            inventory_item["size_bytes"],
            MAX_DESCRIPTOR_BYTES,
        )
        try:
            descriptor_text = descriptor_content.decode("utf-8")
            descriptor = json.loads(descriptor_text, object_pairs_hook=_reject_duplicate_members)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"descriptor canônico inválido: {descriptor_identity}") from exc
        failures = _schema_failures(DESCRIPTOR_SCHEMA, descriptor)
        if failures:
            raise ValueError(
                f"descriptor canônico inválido {descriptor_identity}: " + "; ".join(failures)
            )
        if descriptor["constitution_version"] != version:
            raise ValueError(f"descriptor canônico diverge de VERSION: {descriptor_identity}")

        target_identity = _normalize_identity(descriptor["target"]["identity"])
        if target_identity.endswith(CANONICAL_SUFFIX):
            raise ValueError("descriptor canônico não pode usar outro descriptor canônico como target")
        if target_identity in targets_by_identity:
            raise ValueError(f"target identity anunciada por múltiplos descriptors: {target_identity}")
        target_item = inventory_by_path.get(target_identity)
        if target_item is None:
            raise ValueError(f"target do descriptor não está no inventário autorizado: {target_identity}")
        target_content = _read_stable_file(
            project_root,
            target_identity,
            target_item["size_bytes"],
            MAX_TARGET_BYTES,
        )
        target_sha = hashlib.sha256(target_content).hexdigest()
        if target_sha != descriptor["target"]["sha256"]:
            raise ValueError(f"target do descriptor diverge do SHA declarado: {target_identity}")

        target = {
            "identity": target_identity,
            "kind": "build_manifest",
            "sha256": target_sha,
            "surface_kind": "linker_manifest",
            "kind_basis": "declared",
        }
        targets_by_identity[target_identity] = target
        descriptors.append({
            "identity": descriptor_identity,
            "sha256": hashlib.sha256(descriptor_content).hexdigest(),
            "target": deepcopy(target),
        })

    descriptors.sort(key=lambda row: row["identity"])
    targets = sorted(targets_by_identity.values(), key=lambda row: (row["identity"], row["sha256"]))
    undeclared_targets = [
        deepcopy(row) for row in targets if (row["identity"], row["sha256"]) not in declared
    ]

    result = {
        "result_version": 1,
        "constitution_version": version,
        "relation_id": RELATION_ID,
        "discoverer": {
            "id": manifest["id"],
            "version": manifest["version"],
            "implementation_sha256": manifest["implementation_sha256"],
            "manifest_sha256": _canonical_sha256(manifest),
        },
        "inventory": {
            "authorized_inventory_sha256": _canonical_sha256(inventory),
            "canonical_descriptor_discovery": "complete" if inventory_complete else "incomplete",
        },
        "discovery": {
            "descriptor_suffix": CANONICAL_SUFFIX,
            "descriptors": descriptors,
            "targets": targets,
            "undeclared_targets": undeclared_targets,
            "project_relation_coverage_claim": "none",
        },
        "authority": deepcopy(manifest["authority"]),
    }
    failures = _schema_failures(RESULT_SCHEMA, result)
    if failures:
        raise ValueError("relation surface discovery result inválido: " + "; ".join(failures))
    return result


def validate_discovery_result(
    result: dict,
    config_path: Path,
    project_root: Path,
    declaration: dict | None = None,
) -> list[str]:
    failures = _schema_failures(RESULT_SCHEMA, result)
    if failures:
        return failures
    try:
        expected = discover_relation_surfaces(config_path, project_root, declaration)
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    if result != expected:
        return ["relation surface discovery result diverge da recomputação determinística"]
    return []
