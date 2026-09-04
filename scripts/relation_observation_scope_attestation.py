#!/usr/bin/env python3
"""Atesta completude de um escopo fechado de observacao sem afirmar coverage global da relation."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from scripts.provenance_semantic_interpretation import interpret_observed_provenance
from scripts.semantic_relation_evidence_aggregation import (
    aggregate_semantic_relation_evidence,
    validate_aggregation,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "VERSION"
MANIFEST = ROOT / "governance" / "relation-observation-scope-attestor.yaml"
MANIFEST_SCHEMA = ROOT / "schema" / "relation-observation-scope-attestor-manifest.schema.json"
SCOPE_SCHEMA = ROOT / "schema" / "relation-observation-scope.schema.json"
ATTESTATION_SCHEMA = ROOT / "schema" / "relation-observation-scope-attestation.schema.json"
AGGREGATION_SCHEMA = ROOT / "schema" / "semantic-relation-evidence-aggregation.schema.json"
SEMANTIC_TAXONOMY = ROOT / "governance" / "semantic-relation-taxonomy.yaml"
SEMANTIC_TAXONOMY_SCHEMA = ROOT / "schema" / "semantic-relation-taxonomy.schema.json"
IMPLEMENTATION = Path(__file__).resolve()
ATTESTOR_ID = "evolutive.semantic.relation_observation_scope_attestor"
ATTESTOR_VERSION = "0.1.0"
RELATION_ID = "ffi_native_linkage"


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


def validate_scope_attestor_authority() -> dict:
    manifest = _load_yaml(MANIFEST)
    failures = _schema_failures(MANIFEST_SCHEMA, manifest)
    if failures:
        raise ValueError("manifesto do scope attestor invalido: " + "; ".join(failures))
    version = VERSION.read_text(encoding="ascii").strip()
    if manifest["constitution_version"] != version:
        raise ValueError("scope attestor diverge de VERSION")
    if manifest["id"] != ATTESTOR_ID or manifest["version"] != ATTESTOR_VERSION:
        raise ValueError("identidade do scope attestor diverge do canonico")
    expected_authority = {
        "scope_attestation_only": True,
        "may_assert_scope_completeness": True,
        "may_assert_project_relation_coverage": False,
        "may_assert_complete_rule_semantics": False,
        "may_assert_rule_outcome": False,
        "may_change_rule_status": False,
    }
    if manifest["authority"] != expected_authority:
        raise ValueError("authority do scope attestor diverge do fence canonico")
    actual = _implementation_sha256(IMPLEMENTATION)
    if manifest["implementation_sha256"] != actual:
        raise ValueError(
            "implementation_sha256 do scope attestor diverge: "
            f"esperado {manifest['implementation_sha256']}, atual {actual}"
        )
    return manifest


def _validated_taxonomy(version: str) -> dict:
    taxonomy = _load_yaml(SEMANTIC_TAXONOMY)
    failures = _schema_failures(SEMANTIC_TAXONOMY_SCHEMA, taxonomy)
    if failures:
        raise ValueError("taxonomia semantica invalida: " + "; ".join(failures))
    if taxonomy["constitution_version"] != version:
        raise ValueError("taxonomia semantica diverge de VERSION")
    relation_ids = [relation["id"] for relation in taxonomy["relations"]]
    if len(relation_ids) != len(set(relation_ids)):
        raise ValueError("taxonomia semantica contem relation id duplicado")
    if RELATION_ID not in set(relation_ids):
        raise ValueError("ffi_native_linkage ausente da taxonomia semantica atual")
    return taxonomy


def _validate_scope(scope: dict, version: str) -> None:
    failures = _schema_failures(SCOPE_SCHEMA, scope)
    if failures:
        raise ValueError("relation observation scope invalido: " + "; ".join(failures))
    if scope["constitution_version"] != version:
        raise ValueError("scope diverge de VERSION")
    identities = [item["identity"] for item in scope["manifests"]]
    if len(identities) != len(set(identities)):
        raise ValueError("scope contem manifest identity duplicada")


def _normalized_scope(scope: dict) -> dict:
    normalized = deepcopy(scope)
    normalized["manifests"] = sorted(
        normalized["manifests"],
        key=lambda item: (item["identity"], item["sha256"]),
    )
    return normalized


def _bundle_manifest_key(bundle: dict) -> tuple[str, str]:
    brokered = bundle.get("brokered_manifest")
    if not isinstance(brokered, dict):
        raise ValueError("bundle sem brokered_manifest valido")
    identity = brokered.get("identity")
    digest = brokered.get("sha256")
    if not isinstance(identity, str) or not identity:
        raise ValueError("brokered_manifest identity invalida")
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("brokered_manifest sha256 invalido")
    return identity, digest


def attest_relation_observation_scope(scope: dict, bundles: list[dict], aggregation: dict) -> dict:
    manifest = validate_scope_attestor_authority()
    version = manifest["constitution_version"]
    _validate_scope(scope, version)
    normalized_scope = _normalized_scope(scope)
    taxonomy = _validated_taxonomy(version)

    aggregation_failures = _schema_failures(AGGREGATION_SCHEMA, aggregation)
    if aggregation_failures:
        raise ValueError("semantic relation evidence aggregation invalida: " + "; ".join(aggregation_failures))
    if not isinstance(bundles, list):
        raise ValueError("bundles precisa ser lista")

    provided_keys: list[tuple[str, str]] = []
    positive_bundles: list[dict] = []
    positive_interpretations = 0
    positive_occurrences = 0

    for bundle in bundles:
        if not isinstance(bundle, dict):
            raise ValueError("bundle de scope invalido")
        key = _bundle_manifest_key(bundle)
        if key in provided_keys:
            raise ValueError("bundle duplicado para o mesmo brokered manifest")
        provided_keys.append(key)

        required = {
            "brokered_manifest", "authorized_artifacts", "provenance_evidence",
            "trust_attestation", "semantic_interpretation",
        }
        if set(bundle) != required:
            raise ValueError("bundle de scope possui shape invalido")

        expected = interpret_observed_provenance(
            bundle["brokered_manifest"],
            bundle["authorized_artifacts"],
            bundle["provenance_evidence"],
            bundle["trust_attestation"],
        )
        if expected != bundle["semantic_interpretation"]:
            raise ValueError("semantic interpretation diverge da recomputacao fresca")

        for item in expected["results"]:
            if item["semantic_relation"] != RELATION_ID:
                raise ValueError("scope attestor v0.1.0 recebeu semantic relation fora de ffi_native_linkage")
        if expected["results"]:
            positive_bundles.append(bundle)
            positive_interpretations += 1
            positive_occurrences += len(expected["results"])

    if not positive_bundles:
        raise ValueError(
            "scope attestor v0.1.0 exige ao menos uma interpretation positiva; "
            "ausencia de evidencia nao pode ser convertida em claim negativo"
        )

    aggregation_failures = validate_aggregation(aggregation, positive_bundles)
    if aggregation_failures:
        raise ValueError("aggregation nao corresponde aos bundles positivos: " + "; ".join(aggregation_failures))

    declared_keys = [(item["identity"], item["sha256"]) for item in normalized_scope["manifests"]]
    declared_scope_matches_bundles = set(declared_keys) == set(provided_keys) and len(declared_keys) == len(provided_keys)

    aggregated_interpretations = len(aggregation["subject"]["interpretation_sha256s"])
    aggregated_occurrences = sum(len(row["occurrences"]) for row in aggregation["relations"])
    relation_rows = [row for row in aggregation["relations"] if row["relation_id"] == RELATION_ID]
    if len(relation_rows) != 1 or len(aggregation["relations"]) != 1:
        raise ValueError("scope attestor v0.1.0 aceita apenas aggregation de ffi_native_linkage")

    criteria = {
        "declared_scope_matches_bundles": declared_scope_matches_bundles,
        "all_scope_bundles_recomputable": True,
        "all_positive_interpretations_aggregated": (
            aggregated_interpretations == positive_interpretations
            and aggregated_occurrences == positive_occurrences
        ),
    }
    scope_coverage = "complete" if all(criteria.values()) else "incomplete"

    attestation = {
        "attestation_version": 1,
        "constitution_version": version,
        "subject": {
            "scope_sha256": _canonical_sha256(normalized_scope),
            "aggregation_sha256": _canonical_sha256(aggregation),
            "semantic_taxonomy_sha256": _canonical_sha256(taxonomy),
        },
        "scope": {
            "scope_type": normalized_scope["scope_type"],
            "relation_id": normalized_scope["relation_id"],
            "manifests": deepcopy(normalized_scope["manifests"]),
        },
        "attestor": {
            "id": manifest["id"],
            "version": manifest["version"],
            "implementation_sha256": manifest["implementation_sha256"],
            "manifest_sha256": _canonical_sha256(manifest),
        },
        "evaluation": {
            "scope_coverage": scope_coverage,
            "criteria": criteria,
            "counts": {
                "declared_manifests": len(declared_keys),
                "provided_bundles": len(provided_keys),
                "positive_interpretations": positive_interpretations,
                "aggregated_interpretations": aggregated_interpretations,
                "positive_occurrences": positive_occurrences,
                "aggregated_occurrences": aggregated_occurrences,
            },
            "project_relation_coverage_claim": "none",
        },
        "authority": deepcopy(manifest["authority"]),
    }
    failures = _schema_failures(ATTESTATION_SCHEMA, attestation)
    if failures:
        raise ValueError("relation observation scope attestation invalida: " + "; ".join(failures))
    return attestation


def validate_scope_attestation(attestation: dict, scope: dict, bundles: list[dict], aggregation: dict) -> list[str]:
    failures = _schema_failures(ATTESTATION_SCHEMA, attestation)
    if failures:
        return failures
    try:
        expected = attest_relation_observation_scope(scope, bundles, aggregation)
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    if attestation != expected:
        return ["relation observation scope attestation diverge da recomputacao deterministica"]
    return []
