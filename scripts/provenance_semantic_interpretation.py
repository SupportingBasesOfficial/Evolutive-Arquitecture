#!/usr/bin/env python3
"""Interpreta provenance observada em evidência semântica local e governada."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from scripts.provenance_producer_trust import validate_observed_attestation

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "VERSION"
POLICY = ROOT / "governance" / "provenance-semantic-interpretation-policy.yaml"
INTERPRETER_MANIFEST = ROOT / "governance" / "provenance-semantic-interpreter.yaml"
INTERPRETER_MANIFEST_SCHEMA = ROOT / "schema" / "provenance-semantic-interpreter-manifest.schema.json"
RESULT_SCHEMA = ROOT / "schema" / "provenance-semantic-interpretation.schema.json"
SEMANTIC_TAXONOMY = ROOT / "governance" / "semantic-relation-taxonomy.yaml"
PROVENANCE_MAPPING = ROOT / "governance" / "build-time-semantic-mapping.yaml"
IMPLEMENTATION = Path(__file__).resolve()
INTERPRETER_ID = "evolutive.provenance.semantic_interpreter"
INTERPRETER_VERSION = "0.1.0"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _implementation_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def validate_interpreter_contract() -> tuple[dict, dict]:
    version = VERSION.read_text(encoding="ascii").strip()
    manifest = _load_yaml(INTERPRETER_MANIFEST)
    manifest_schema = _load_json(INTERPRETER_MANIFEST_SCHEMA)
    Draft202012Validator.check_schema(manifest_schema)
    failures = sorted(error.message for error in Draft202012Validator(manifest_schema).iter_errors(manifest))
    if failures:
        raise ValueError("manifesto do semantic interpreter inválido: " + "; ".join(failures))
    if manifest["constitution_version"] != version:
        raise ValueError("semantic interpreter diverge de VERSION")
    if manifest["id"] != INTERPRETER_ID or manifest["version"] != INTERPRETER_VERSION:
        raise ValueError("identidade do semantic interpreter diverge do canônico")
    actual_digest = _implementation_sha256(IMPLEMENTATION)
    if manifest["implementation_sha256"] != actual_digest:
        raise ValueError(
            "implementation_sha256 do semantic interpreter diverge: "
            f"esperado {manifest['implementation_sha256']}, atual {actual_digest}"
        )

    policy = _load_yaml(POLICY)
    taxonomy = _load_yaml(SEMANTIC_TAXONOMY)
    mapping = _load_yaml(PROVENANCE_MAPPING)
    if policy.get("constitution_version") != version:
        raise ValueError("policy de interpretação diverge de VERSION")
    if policy.get("authority") != {
        "semantic_interpretation_only": True,
        "may_assert_semantic_relation": True,
        "may_assert_rule_outcome": False,
        "may_assert_semantic_exhaustiveness": False,
        "may_assert_complete_rule_semantics": False,
    }:
        raise ValueError("authority da policy diverge do fence canônico")

    relation_ids = {relation["id"] for relation in taxonomy["relations"]}
    mapping_index = {
        entry["provenance_class"]: set(entry["candidate_relations"])
        for entry in mapping["mappings"]
    }
    profiles = policy.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("policy precisa declarar profiles")
    seen_profiles: set[str] = set()
    for profile in profiles:
        required = {
            "id", "provenance_class", "semantic_relation", "required_observation_basis",
            "required_trust_verdict", "allowed_producer_ids", "interpretation_strength",
            "relation_scope", "rationale",
        }
        if not isinstance(profile, dict) or set(profile) != required:
            raise ValueError("profile de interpretação possui shape inválido")
        if profile["id"] in seen_profiles:
            raise ValueError("profile de interpretação duplicado")
        seen_profiles.add(profile["id"])
        if profile["semantic_relation"] not in relation_ids:
            raise ValueError("profile referencia semantic relation desconhecida")
        candidates = mapping_index.get(profile["provenance_class"])
        if candidates is None or profile["semantic_relation"] not in candidates:
            raise ValueError("profile não é autorizado pelo mapping de provenance")
        if profile["required_observation_basis"] != "observed":
            raise ValueError("v0.1.0 aceita somente provenance observada")
        if profile["required_trust_verdict"] != "verified":
            raise ValueError("v0.1.0 exige trust verdict verified")
        if profile["allowed_producer_ids"] != ["evolutive.provenance.observed_manifest_reader"]:
            raise ValueError("v0.1.0 aceita somente observed_manifest_reader")
        if profile["interpretation_strength"] != "direct" or profile["relation_scope"] != "transformation_local":
            raise ValueError("v0.1.0 exige interpretação direta e local")
    return manifest, policy


def interpret_observed_provenance(
    brokered_manifest: dict,
    authorized_artifacts: list[dict],
    provenance_evidence: dict,
    trust_attestation: dict,
) -> dict:
    manifest, policy = validate_interpreter_contract()
    validate_observed_attestation(
        trust_attestation,
        brokered_manifest,
        authorized_artifacts,
        provenance_evidence,
    )
    if trust_attestation["evaluation"]["verdict"] != "verified":
        raise ValueError("trust attestation não está verified")
    if trust_attestation["producer"]["observation_basis"] != "observed":
        raise ValueError("semantic interpretation exige observation_basis observed")

    profiles = {
        (profile["provenance_class"], profile["semantic_relation"]): profile
        for profile in policy["profiles"]
    }
    results: list[dict] = []
    for transformation in provenance_evidence["transformations"]:
        if transformation["observation_basis"] != "observed":
            continue
        for relation in transformation["candidate_relations"]:
            profile = profiles.get((transformation["provenance_class"], relation))
            if profile is None:
                continue
            if provenance_evidence["producer"]["id"] not in profile["allowed_producer_ids"]:
                continue
            results.append({
                "transformation_id": transformation["id"],
                "provenance_class": transformation["provenance_class"],
                "semantic_relation": relation,
                "profile_id": profile["id"],
                "verdict": "proven",
                "scope": "transformation_local",
            })

    result = {
        "interpretation_version": 1,
        "constitution_version": manifest["constitution_version"],
        "subject": {
            "provenance_evidence_sha256": _canonical_sha256(provenance_evidence),
            "trust_attestation_sha256": _canonical_sha256(trust_attestation),
            "policy_sha256": _canonical_sha256(policy),
            "semantic_taxonomy_sha256": _canonical_sha256(_load_yaml(SEMANTIC_TAXONOMY)),
            "provenance_mapping_sha256": _canonical_sha256(_load_yaml(PROVENANCE_MAPPING)),
        },
        "interpreter": {
            "id": manifest["id"],
            "version": manifest["version"],
            "implementation_sha256": manifest["implementation_sha256"],
            "manifest_sha256": _canonical_sha256(manifest),
        },
        "results": results,
        "authority": {
            "semantic_evidence_only": True,
            "may_assert_rule_outcome": False,
            "may_assert_semantic_exhaustiveness": False,
            "may_assert_complete_rule_semantics": False,
        },
    }
    schema = _load_json(RESULT_SCHEMA)
    Draft202012Validator.check_schema(schema)
    failures = sorted(error.message for error in Draft202012Validator(schema).iter_errors(result))
    if failures:
        raise ValueError("resultado de semantic interpretation inválido: " + "; ".join(failures))
    return result
