#!/usr/bin/env python3
"""Atesta alinhamento de superfícies declaradas sem afirmar project-level relation coverage."""

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
MANIFEST = ROOT / "governance" / "relation-surface-inventory-attestor.yaml"
MANIFEST_SCHEMA = ROOT / "schema" / "relation-surface-inventory-attestor-manifest.schema.json"
DECLARATION_SCHEMA = ROOT / "schema" / "relation-surface-inventory-declaration.schema.json"
ATTESTATION_SCHEMA = ROOT / "schema" / "relation-surface-inventory-attestation.schema.json"
IMPLEMENTATION = Path(__file__).resolve()
ATTESTOR_ID = "evolutive.semantic.relation_surface_inventory_attestor"
ATTESTOR_VERSION = "0.1.0"
RELATION_ID = "ffi_native_linkage"
MAX_SURFACE_BYTES = 1_048_576


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


def validate_attestor_authority() -> dict:
    manifest = _load_yaml(MANIFEST)
    failures = _schema_failures(MANIFEST_SCHEMA, manifest)
    if failures:
        raise ValueError("manifesto do relation surface inventory attestor inválido: " + "; ".join(failures))
    version = VERSION.read_text(encoding="ascii").strip()
    if manifest["constitution_version"] != version:
        raise ValueError("relation surface inventory attestor diverge de VERSION")
    if manifest["id"] != ATTESTOR_ID or manifest["version"] != ATTESTOR_VERSION:
        raise ValueError("identidade do relation surface inventory attestor diverge do canônico")
    expected_authority = {
        "inventory_attestation_only": True,
        "may_assert_declared_surface_inventory_alignment": True,
        "may_assert_project_relation_coverage": False,
        "may_assert_complete_rule_semantics": False,
        "may_assert_rule_outcome": False,
        "may_change_rule_status": False,
    }
    if manifest["authority"] != expected_authority:
        raise ValueError("authority do relation surface inventory attestor diverge do fence canônico")
    actual = _implementation_sha256(IMPLEMENTATION)
    if manifest["implementation_sha256"] != actual:
        raise ValueError(
            "implementation_sha256 do relation surface inventory attestor diverge: "
            f"esperado {manifest['implementation_sha256']}, atual {actual}"
        )
    return manifest


def _normalize_identity(identity: str) -> str:
    if not isinstance(identity, str) or not identity or "\\" in identity:
        raise ValueError("surface identity deve ser path POSIX relativo")
    path = PurePosixPath(identity)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("surface identity inválida ou escapando do projeto")
    normalized = path.as_posix()
    if normalized != identity:
        raise ValueError("surface identity deve estar em forma POSIX canônica")
    return normalized


def _validated_declaration(declaration: dict, version: str) -> dict:
    failures = _schema_failures(DECLARATION_SCHEMA, declaration)
    if failures:
        raise ValueError("relation surface inventory declaration inválida: " + "; ".join(failures))
    if declaration["constitution_version"] != version:
        raise ValueError("relation surface inventory declaration diverge de VERSION")
    if declaration["relation_id"] != RELATION_ID:
        raise ValueError("v0.1.0 aceita apenas ffi_native_linkage")
    identities: set[str] = set()
    surfaces = []
    for item in declaration["surfaces"]:
        identity = _normalize_identity(item["identity"])
        if identity in identities:
            raise ValueError("relation surface inventory declaration contém identity duplicada")
        identities.add(identity)
        surfaces.append({
            "identity": identity,
            "surface_kind": item["surface_kind"],
            "kind_basis": item["kind_basis"],
            "sha256": item["sha256"],
        })
    return {
        "declaration_version": declaration["declaration_version"],
        "constitution_version": declaration["constitution_version"],
        "relation_id": declaration["relation_id"],
        "surfaces": sorted(surfaces, key=lambda row: (row["identity"], row["sha256"])),
    }


def attest_relation_surface_inventory(
    declaration: dict,
    config_path: Path,
    project_root: Path,
) -> dict:
    manifest = validate_attestor_authority()
    version = manifest["constitution_version"]
    normalized_declaration = _validated_declaration(declaration, version)
    inventory = build_inventory(config_path, project_root)
    project_root = project_root.resolve()
    inventory_by_path = {item["path"]: item for item in inventory["files"]}

    no_inventory_gaps = not inventory["missing_roots"] and not inventory["skipped_symlinks"]
    all_authorized = True
    all_regular = True
    all_snapshot_match = True
    all_within_bound = True
    all_hash_match = True
    authorized_count = 0
    hash_verified_count = 0

    for surface in normalized_declaration["surfaces"]:
        identity = surface["identity"]
        inventory_item = inventory_by_path.get(identity)
        if inventory_item is None:
            all_authorized = False
            all_regular = False
            all_snapshot_match = False
            all_within_bound = False
            all_hash_match = False
            continue
        authorized_count += 1
        candidate = project_root / identity
        if candidate.is_symlink() or not candidate.is_file():
            all_regular = False
            all_snapshot_match = False
            all_hash_match = False
            continue
        resolved = candidate.resolve()
        try:
            resolved.relative_to(project_root)
        except ValueError:
            all_regular = False
            all_snapshot_match = False
            all_hash_match = False
            continue
        before_size = candidate.stat().st_size
        if before_size != inventory_item["size_bytes"]:
            all_snapshot_match = False
            all_hash_match = False
            continue
        if before_size > MAX_SURFACE_BYTES:
            all_within_bound = False
            all_hash_match = False
            continue
        content = candidate.read_bytes()
        after_size = candidate.stat().st_size
        if after_size != before_size or len(content) != before_size:
            all_snapshot_match = False
            all_hash_match = False
            continue
        actual_sha = hashlib.sha256(content).hexdigest()
        if actual_sha != surface["sha256"]:
            all_hash_match = False
            continue
        hash_verified_count += 1

    criteria = {
        "authorized_inventory_has_no_gaps": no_inventory_gaps,
        "all_declared_surfaces_authorized": all_authorized,
        "all_declared_surfaces_regular": all_regular,
        "all_declared_surfaces_match_inventory_snapshot": all_snapshot_match,
        "all_declared_surfaces_within_size_bound": all_within_bound,
        "all_declared_surface_hashes_match": all_hash_match,
    }
    reason_by_criterion = {
        "authorized_inventory_has_no_gaps": "authorized_inventory_gap",
        "all_declared_surfaces_authorized": "surface_not_authorized",
        "all_declared_surfaces_regular": "surface_not_regular",
        "all_declared_surfaces_match_inventory_snapshot": "surface_snapshot_mismatch",
        "all_declared_surfaces_within_size_bound": "surface_size_bound_exceeded",
        "all_declared_surface_hashes_match": "surface_hash_mismatch",
    }
    reasons = [reason_by_criterion[name] for name, satisfied in criteria.items() if not satisfied]
    aligned = all(criteria.values())

    attestation = {
        "attestation_version": 1,
        "constitution_version": version,
        "subject": {
            "declaration_sha256": _canonical_sha256(normalized_declaration),
            "authorized_inventory_sha256": _canonical_sha256(inventory),
        },
        "scope": {
            "relation_id": RELATION_ID,
            "surfaces": deepcopy(normalized_declaration["surfaces"]),
        },
        "attestor": {
            "id": manifest["id"],
            "version": manifest["version"],
            "implementation_sha256": manifest["implementation_sha256"],
            "manifest_sha256": _canonical_sha256(manifest),
        },
        "evaluation": {
            "declared_surface_inventory": "aligned" if aligned else "misaligned",
            "criteria": criteria,
            "reasons": reasons,
            "counts": {
                "declared_surfaces": len(normalized_declaration["surfaces"]),
                "authorized_surfaces": authorized_count,
                "hash_verified_surfaces": hash_verified_count,
            },
            "project_relation_coverage_claim": "none",
        },
        "authority": deepcopy(manifest["authority"]),
    }
    failures = _schema_failures(ATTESTATION_SCHEMA, attestation)
    if failures:
        raise ValueError("relation surface inventory attestation inválida: " + "; ".join(failures))
    return attestation


def validate_attestation(attestation: dict, declaration: dict, config_path: Path, project_root: Path) -> list[str]:
    failures = _schema_failures(ATTESTATION_SCHEMA, attestation)
    if failures:
        return failures
    try:
        expected = attest_relation_surface_inventory(declaration, config_path, project_root)
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    if attestation != expected:
        return ["relation surface inventory attestation diverge da recomputação determinística"]
    return []
