#!/usr/bin/env python3
"""Agrega evidência semântica local sem produzir claim de coverage ou rule outcome."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from scripts.provenance_semantic_interpretation import interpret_observed_provenance

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "VERSION"
MANIFEST = ROOT / "governance" / "semantic-relation-evidence-aggregator.yaml"
RESULT_SCHEMA = ROOT / "schema" / "semantic-relation-evidence-aggregation.schema.json"
SEMANTIC_TAXONOMY = ROOT / "governance" / "semantic-relation-taxonomy.yaml"
IMPLEMENTATION = Path(__file__).resolve()
AGGREGATOR_ID = "evolutive.semantic.relation_evidence_aggregator"
AGGREGATOR_VERSION = "0.1.0"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _implementation_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_aggregator_authority() -> dict:
    manifest = _load_yaml(MANIFEST)
    version = VERSION.read_text(encoding="ascii").strip()
    expected_keys = {"manifest_version", "id", "version", "constitution_version", "implementation_sha256", "authority"}
    if not isinstance(manifest, dict) or set(manifest) != expected_keys:
        raise ValueError("manifesto do relation evidence aggregator possui shape inválido")
    if manifest["manifest_version"] != 1:
        raise ValueError("manifest_version do relation evidence aggregator inválida")
    if manifest["constitution_version"] != version:
        raise ValueError("relation evidence aggregator diverge de VERSION")
    if manifest["id"] != AGGREGATOR_ID or manifest["version"] != AGGREGATOR_VERSION:
        raise ValueError("identidade do relation evidence aggregator diverge do canônico")
    expected_authority = {
        "relation_evidence_aggregation_only": True,
        "may_assert_relation_coverage": False,
        "may_assert_complete_rule_semantics": False,
        "may_assert_rule_outcome": False,
        "may_change_rule_status": False,
    }
    if manifest["authority"] != expected_authority:
        raise ValueError("authority do relation evidence aggregator diverge do fence canônico")
    actual = _implementation_sha256(IMPLEMENTATION)
    if manifest["implementation_sha256"] != actual:
        raise ValueError(
            "implementation_sha256 do relation evidence aggregator diverge: "
            f"esperado {manifest['implementation_sha256']}, atual {actual}"
        )
    return manifest


def aggregate_semantic_relation_evidence(bundles: list[dict]) -> dict:
    manifest = validate_aggregator_authority()
    if not isinstance(bundles, list):
        raise ValueError("bundles precisa ser lista")

    taxonomy = _load_yaml(SEMANTIC_TAXONOMY)
    relation_ids = {relation["id"] for relation in taxonomy["relations"]}
    interpretation_hashes: list[str] = []
    relation_occurrences: dict[str, list[dict]] = {}
    seen_interpretations: set[str] = set()
    seen_occurrences: set[tuple[str, str, str]] = set()

    for bundle in bundles:
        required = {
            "brokered_manifest", "authorized_artifacts", "provenance_evidence",
            "trust_attestation", "semantic_interpretation",
        }
        if not isinstance(bundle, dict) or set(bundle) != required:
            raise ValueError("bundle semântico possui shape inválido")
        expected = interpret_observed_provenance(
            bundle["brokered_manifest"],
            bundle["authorized_artifacts"],
            bundle["provenance_evidence"],
            bundle["trust_attestation"],
        )
        if expected != bundle["semantic_interpretation"]:
            raise ValueError("semantic interpretation diverge da recomputação fresca")

        interpretation_sha = _canonical_sha256(expected)
        if interpretation_sha in seen_interpretations:
            raise ValueError("semantic interpretation duplicada na agregação")
        seen_interpretations.add(interpretation_sha)
        interpretation_hashes.append(interpretation_sha)

        provenance_sha = expected["subject"]["provenance_evidence_sha256"]
        for item in expected["results"]:
            relation_id = item["semantic_relation"]
            if relation_id not in relation_ids:
                raise ValueError("semantic interpretation referencia relation fora da taxonomia atual")
            key = (provenance_sha, item["transformation_id"], relation_id)
            if key in seen_occurrences:
                raise ValueError("occurrence semântica duplicada na agregação")
            seen_occurrences.add(key)
            relation_occurrences.setdefault(relation_id, []).append({
                "source_interpretation_sha256": interpretation_sha,
                "provenance_evidence_sha256": provenance_sha,
                "transformation_id": item["transformation_id"],
                "provenance_class": item["provenance_class"],
                "profile_id": item["profile_id"],
                "scope": item["scope"],
                "inputs": deepcopy(item["inputs"]),
                "outputs": deepcopy(item["outputs"]),
            })

    relations = []
    for relation_id in sorted(relation_occurrences):
        occurrences = sorted(
            relation_occurrences[relation_id],
            key=lambda row: (
                row["provenance_evidence_sha256"],
                row["transformation_id"],
                row["profile_id"],
            ),
        )
        relations.append({
            "relation_id": relation_id,
            "has_proven_local_evidence": True,
            "coverage_claim": "none",
            "occurrences": occurrences,
        })

    result = {
        "aggregation_version": 1,
        "constitution_version": manifest["constitution_version"],
        "subject": {
            "interpretation_sha256s": sorted(interpretation_hashes),
            "semantic_taxonomy_sha256": _canonical_sha256(taxonomy),
        },
        "aggregator": {
            "id": manifest["id"],
            "version": manifest["version"],
            "implementation_sha256": manifest["implementation_sha256"],
            "manifest_sha256": _canonical_sha256(manifest),
        },
        "relations": relations,
        "authority": deepcopy(manifest["authority"]),
    }
    schema = _load_json(RESULT_SCHEMA)
    Draft202012Validator.check_schema(schema)
    failures = sorted(error.message for error in Draft202012Validator(schema).iter_errors(result))
    if failures:
        raise ValueError("semantic relation evidence aggregation inválida: " + "; ".join(failures))
    return result


def validate_aggregation(aggregation: dict, bundles: list[dict]) -> list[str]:
    schema = _load_json(RESULT_SCHEMA)
    failures = sorted(error.message for error in Draft202012Validator(schema).iter_errors(aggregation))
    if failures:
        return failures
    try:
        expected = aggregate_semantic_relation_evidence(bundles)
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    if aggregation != expected:
        return ["semantic relation evidence aggregation diverge da recomputação determinística"]
    return []
