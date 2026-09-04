#!/usr/bin/env python3
"""Reproduz evidence de provenance e emite attestation de confiança limitada."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from evolutive.provenance.declared_manifest_verifier import (
    PRODUCER_ID as DECLARED_PRODUCER_ID,
    PRODUCER_VERSION as DECLARED_PRODUCER_VERSION,
    verify as verify_declared,
)
from evolutive.provenance.observed_manifest_reader import (
    PRODUCER_ID as OBSERVED_PRODUCER_ID,
    PRODUCER_VERSION as OBSERVED_PRODUCER_VERSION,
    observe as observe_manifest,
)
from scripts.validate_build_time_provenance_governance import (
    EVIDENCE_SCHEMA as BUILD_TIME_EVIDENCE_SCHEMA,
    PROVENANCE_TAXONOMY,
    SEMANTIC_MAPPING,
    validate_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "VERSION"
MANIFEST_SCHEMA = ROOT / "schema" / "provenance-producer-manifest.schema.json"
OBSERVED_MANIFEST_SCHEMA = ROOT / "schema" / "observed-provenance-manifest.schema.json"
ATTESTATION_SCHEMA = ROOT / "schema" / "provenance-producer-trust-attestation.schema.json"
ATTESTOR_MANIFEST_SCHEMA = ROOT / "schema" / "provenance-producer-trust-attestor-manifest.schema.json"
DECLARED_PRODUCER_MANIFEST = ROOT / "producers" / "declared-manifest-verifier.yaml"
DECLARED_PRODUCER_IMPLEMENTATION = ROOT / "evolutive" / "provenance" / "declared_manifest_verifier.py"
OBSERVED_PRODUCER_MANIFEST = ROOT / "producers" / "observed-manifest-reader.yaml"
OBSERVED_PRODUCER_IMPLEMENTATION = ROOT / "evolutive" / "provenance" / "observed_manifest_reader.py"
ATTESTOR_MANIFEST = ROOT / "governance" / "provenance-producer-trust-attestor.yaml"
ATTESTOR_IMPLEMENTATION = Path(__file__).resolve()
BUILD_TIME_VALIDATOR_IMPLEMENTATION = ROOT / "scripts" / "validate_build_time_provenance_governance.py"
ATTESTOR_ID = "evolutive.provenance.producer_trust_attestor"
ATTESTOR_VERSION = "0.2.0"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _implementation_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _governance_context_sha256() -> str:
    context = {
        "build_time_evidence_schema": _load_json(BUILD_TIME_EVIDENCE_SCHEMA),
        "observed_provenance_manifest_schema": _load_json(OBSERVED_MANIFEST_SCHEMA),
        "provenance_taxonomy": _load_yaml(PROVENANCE_TAXONOMY),
        "semantic_mapping": _load_yaml(SEMANTIC_MAPPING),
        "build_time_validator_implementation_sha256": _implementation_sha256(BUILD_TIME_VALIDATOR_IMPLEMENTATION),
        "producer_manifest_schema": _load_json(MANIFEST_SCHEMA),
        "trust_attestation_schema": _load_json(ATTESTATION_SCHEMA),
        "trust_attestor_manifest_schema": _load_json(ATTESTOR_MANIFEST_SCHEMA),
    }
    return _canonical_sha256(context)


def _normalized_authorized_artifacts(authorized_artifacts: list[dict]) -> list[dict]:
    if not isinstance(authorized_artifacts, list):
        raise ValueError("authorized_artifacts precisa ser lista")
    normalized: list[dict] = []
    for artifact in authorized_artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {"identity", "kind", "sha256"}:
            raise ValueError("artifact autorizado precisa conter somente identity, kind e sha256")
        identity, kind, sha256 = artifact["identity"], artifact["kind"], artifact["sha256"]
        if not all(isinstance(value, str) and value for value in (identity, kind, sha256)):
            raise ValueError("artifact autorizado incompleto")
        if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
            raise ValueError("artifact autorizado com sha256 inválido")
        normalized.append({"identity": identity, "kind": kind, "sha256": sha256})
    return sorted(normalized, key=lambda item: (item["identity"], item["kind"], item["sha256"]))


def validate_attestor_authority(manifest_path: Path = ATTESTOR_MANIFEST) -> dict:
    manifest = _load_yaml(manifest_path)
    schema = _load_json(ATTESTOR_MANIFEST_SCHEMA)
    Draft202012Validator.check_schema(schema)
    failures = sorted(error.message for error in Draft202012Validator(schema).iter_errors(manifest))
    if failures:
        raise ValueError("manifesto do trust attestor inválido: " + "; ".join(failures))
    version = VERSION.read_text(encoding="ascii").strip()
    if manifest["constitution_version"] != version:
        raise ValueError("trust attestor diverge de VERSION")
    if manifest["id"] != ATTESTOR_ID or manifest["version"] != ATTESTOR_VERSION:
        raise ValueError("identidade do trust attestor diverge do canônico")
    if manifest["authority"] != {
        "trust_only": True,
        "may_assert_semantic_relation": False,
        "may_assert_rule_outcome": False,
        "may_assert_semantic_exhaustiveness": False,
    }:
        raise ValueError("authority do trust attestor diverge do fence canônico")
    actual_digest = _implementation_sha256(ATTESTOR_IMPLEMENTATION)
    if manifest["implementation_sha256"] != actual_digest:
        raise ValueError(
            "implementation_sha256 do trust attestor diverge: "
            f"esperado {manifest['implementation_sha256']}, atual {actual_digest}"
        )
    return manifest


def _validate_producer_manifest(
    manifest_path: Path,
    implementation_path: Path,
    expected_id: str,
    expected_version: str,
    expected_entrypoint: str,
    expected_basis: str,
) -> dict:
    manifest = _load_yaml(manifest_path)
    schema = _load_json(MANIFEST_SCHEMA)
    Draft202012Validator.check_schema(schema)
    failures = sorted(error.message for error in Draft202012Validator(schema).iter_errors(manifest))
    if failures:
        raise ValueError("manifesto de producer inválido: " + "; ".join(failures))
    if manifest["constitution_version"] != VERSION.read_text(encoding="ascii").strip():
        raise ValueError("manifesto de producer diverge de VERSION")
    if manifest["id"] != expected_id or manifest["version"] != expected_version:
        raise ValueError("manifesto diverge da identidade da implementação")
    if manifest["runtime"]["entrypoint"] != expected_entrypoint:
        raise ValueError("entrypoint do producer diverge do canônico")
    actual_digest = _implementation_sha256(implementation_path)
    if manifest["runtime"]["implementation_sha256"] != actual_digest:
        raise ValueError(
            "implementation_sha256 do producer diverge: "
            f"esperado {manifest['runtime']['implementation_sha256']}, atual {actual_digest}"
        )
    if manifest["capabilities"] != {
        "network": False,
        "subprocess": False,
        "environment": False,
        "executes_consumer_code": False,
        "observation_basis": expected_basis,
    }:
        raise ValueError("capabilities do producer divergem do fence canônico")
    return manifest


def validate_declared_producer_manifest(manifest_path: Path = DECLARED_PRODUCER_MANIFEST) -> dict:
    return _validate_producer_manifest(
        manifest_path,
        DECLARED_PRODUCER_IMPLEMENTATION,
        DECLARED_PRODUCER_ID,
        DECLARED_PRODUCER_VERSION,
        "evolutive.provenance.declared_manifest_verifier:verify",
        "declared",
    )


def validate_observed_producer_manifest(manifest_path: Path = OBSERVED_PRODUCER_MANIFEST) -> dict:
    return _validate_producer_manifest(
        manifest_path,
        OBSERVED_PRODUCER_IMPLEMENTATION,
        OBSERVED_PRODUCER_ID,
        OBSERVED_PRODUCER_VERSION,
        "evolutive.provenance.observed_manifest_reader:observe",
        "observed",
    )


def validate_producer_manifest(manifest_path: Path = DECLARED_PRODUCER_MANIFEST) -> dict:
    """Compatibilidade: valida o producer declarativo canônico."""
    return validate_declared_producer_manifest(manifest_path)


def _build_attestation(producer_input: dict, normalized_artifacts: list[dict], evidence: dict, producer_manifest: dict, attestor_manifest: dict) -> dict:
    evidence_failures = validate_evidence(evidence)
    if evidence_failures:
        raise ValueError("evidence de provenance inválida: " + "; ".join(evidence_failures))
    if evidence["producer"] != {
        "id": producer_manifest["id"],
        "version": producer_manifest["version"],
        "kind": "provenance_adapter",
    }:
        raise ValueError("evidence não foi emitida pela identidade de producer esperada")
    attestation = {
        "attestation_version": 1,
        "constitution_version": producer_manifest["constitution_version"],
        "subject": {
            "producer_input_sha256": _canonical_sha256(producer_input),
            "authorized_artifacts_sha256": _canonical_sha256(normalized_artifacts),
            "evidence_sha256": _canonical_sha256(evidence),
            "governance_context_sha256": _governance_context_sha256(),
        },
        "producer": {
            "id": producer_manifest["id"],
            "version": producer_manifest["version"],
            "implementation_sha256": producer_manifest["runtime"]["implementation_sha256"],
            "manifest_sha256": _canonical_sha256(producer_manifest),
            "observation_basis": producer_manifest["capabilities"]["observation_basis"],
        },
        "evaluator": {
            "id": attestor_manifest["id"],
            "version": attestor_manifest["version"],
            "implementation_sha256": attestor_manifest["implementation_sha256"],
            "manifest_sha256": _canonical_sha256(attestor_manifest),
        },
        "evaluation": {
            "verdict": "verified",
            "reproduced_exactly": True,
            "capabilities_safe": True,
        },
        "authority": {
            "trust_only": True,
            "may_assert_semantic_relation": False,
            "may_assert_rule_outcome": False,
            "may_assert_semantic_exhaustiveness": False,
        },
    }
    schema = _load_json(ATTESTATION_SCHEMA)
    Draft202012Validator.check_schema(schema)
    failures = sorted(error.message for error in Draft202012Validator(schema).iter_errors(attestation))
    if failures:
        raise ValueError("attestation de producer inválida: " + "; ".join(failures))
    return attestation


def attest_producer_trust(
    declaration: dict,
    authorized_artifacts: list[dict],
    evidence: dict,
    manifest_path: Path = DECLARED_PRODUCER_MANIFEST,
    attestor_manifest_path: Path = ATTESTOR_MANIFEST,
) -> dict:
    attestor_manifest = validate_attestor_authority(attestor_manifest_path)
    producer_manifest = validate_declared_producer_manifest(manifest_path)
    normalized_artifacts = _normalized_authorized_artifacts(authorized_artifacts)
    reproduced = verify_declared(declaration, normalized_artifacts)
    if reproduced != evidence:
        raise ValueError("evidence diverge da reprodução fresca do producer")
    return _build_attestation(declaration, normalized_artifacts, evidence, producer_manifest, attestor_manifest)


def attest_observed_producer_trust(
    brokered_manifest: dict,
    authorized_artifacts: list[dict],
    evidence: dict,
    manifest_path: Path = OBSERVED_PRODUCER_MANIFEST,
    attestor_manifest_path: Path = ATTESTOR_MANIFEST,
) -> dict:
    attestor_manifest = validate_attestor_authority(attestor_manifest_path)
    producer_manifest = validate_observed_producer_manifest(manifest_path)
    normalized_artifacts = _normalized_authorized_artifacts(authorized_artifacts)
    reproduced = observe_manifest(brokered_manifest, normalized_artifacts, _load_json(OBSERVED_MANIFEST_SCHEMA))
    if reproduced != evidence:
        raise ValueError("evidence diverge da reprodução fresca do producer observado")
    return _build_attestation(brokered_manifest, normalized_artifacts, evidence, producer_manifest, attestor_manifest)


def validate_attestation(attestation: dict, declaration: dict, authorized_artifacts: list[dict], evidence: dict) -> None:
    if attestation != attest_producer_trust(declaration, authorized_artifacts, evidence):
        raise ValueError("attestation diverge da reprodução fresca")


def validate_observed_attestation(attestation: dict, brokered_manifest: dict, authorized_artifacts: list[dict], evidence: dict) -> None:
    if attestation != attest_observed_producer_trust(brokered_manifest, authorized_artifacts, evidence):
        raise ValueError("attestation observada diverge da reprodução fresca")
