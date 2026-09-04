#!/usr/bin/env python3
"""Interpreta provenance observada em evidência semântica local e governada."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
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
_ALLOWED_PROFILE = {
    "id": "linker-binding-to-ffi-native-linkage",
    "provenance_class": "linker_binding",
    "semantic_relation": "ffi_native_linkage",
    "required_observation_basis": "observed",
    "required_trust_verdict": "verified",
    "allowed_producer_ids": ["evolutive.provenance.observed_manifest_reader"],
    "interpretation_strength": "direct",
    "relation_scope": "transformation_local",
}


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _implementation_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _validate_policy(policy: dict, version: str) -> None:
    if not isinstance(policy, dict) or set(policy) != {"policy_version", "constitution_version", "authority", "profiles"}:
        raise ValueError("policy de interpretação possui shape top-level inválido")
    if policy["policy_version"] != 1:
        raise ValueError("policy_version não suportada")
    if policy["constitution_version"] != version:
        raise ValueError("policy de interpretação diverge de VERSION")
    if policy["authority"] != {
        "semantic_interpretation_only": True,
        "may_assert_semantic_relation": True,
        "may_assert_rule_outcome": False,
        "may_assert_semantic_exhaustiveness": False,
        "may_assert_complete_rule_semantics": False,
    }:
        raise ValueError("authority da policy diverge do fence canônico")

    profiles = policy["profiles"]
    if not isinstance(profiles, list) or len(profiles) != 1:
        raise ValueError("v0.1.0 autoriza exatamente um profile semântico")
    profile = profiles[0]
    required = set(_ALLOWED_PROFILE) | {"rationale"}
    if not isinstance(profile, dict) or set(profile) != required:
        raise ValueError("profile de interpretação possui shape inválido")
    if not isinstance(profile["rationale"], str) or not profile["rationale"].strip():
        raise ValueError("profile de interpretação exige rationale")
    for key, expected in _ALLOWED_PROFILE.items():
        if profile[key] != expected:
            raise ValueError(f"v0.1.0 não autoriza alteração de {key}")


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
    _validate_policy(policy, version)

    relation_ids = {relation["id"] for relation in taxonomy["relations"]}
    mapping_index = {
        entry["provenance_class"]: set(entry["candidate_relations"])
        for entry in mapping["mappings"]
    }
    profile = policy["profiles"][0]
    if profile["semantic_relation"] not in relation_ids:
        raise ValueError("profile referencia semantic relation desconhecida")
    candidates = mapping_index.get(profile["provenance_class"])
    if candidates is None or profile["semantic_relation"] not in candidates:
        raise ValueError("profile não é autorizado pelo mapping de provenance")
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

    profile = policy["profiles"][0]
    results: list[dict] = []
    for transformation in provenance_evidence["transformations"]:
        if transformation["observation_basis"] != "observed":
            continue
        if transformation["provenance_class"] != profile["provenance_class"]:
            continue
        if profile["semantic_relation"] not in transformation["candidate_relations"]:
            continue
        if provenance_evidence["producer"]["id"] not in profile["allowed_producer_ids"]:
            continue
        results.append({
            "transformation_id": transformation["id"],
            "provenance_class": transformation["provenance_class"],
            "semantic_relation": profile["semantic_relation"],
            "profile_id": profile["id"],
            "verdict": "proven",
            "scope": "transformation_local",
            "inputs": deepcopy(transformation["inputs"]),
            "outputs": deepcopy(transformation["outputs"]),
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
