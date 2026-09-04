#!/usr/bin/env python3
"""Reproduz evidence de provenance e emite attestation de confiança limitada."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from evolutive.provenance.declared_manifest_verifier import (
    PRODUCER_ID,
    PRODUCER_VERSION,
    verify,
)
from scripts.validate_build_time_provenance_governance import validate_evidence

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "VERSION"
MANIFEST_SCHEMA = ROOT / "schema" / "provenance-producer-manifest.schema.json"
ATTESTATION_SCHEMA = ROOT / "schema" / "provenance-producer-trust-attestation.schema.json"
PRODUCER_MANIFEST = ROOT / "producers" / "declared-manifest-verifier.yaml"
PRODUCER_IMPLEMENTATION = ROOT / "evolutive" / "provenance" / "declared_manifest_verifier.py"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _implementation_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate_producer_manifest(manifest_path: Path = PRODUCER_MANIFEST) -> dict:
    manifest = _load_yaml(manifest_path)
    schema = _load_json(MANIFEST_SCHEMA)
    Draft202012Validator.check_schema(schema)
    failures = sorted(error.message for error in Draft202012Validator(schema).iter_errors(manifest))
    if failures:
        raise ValueError("manifesto de producer inválido: " + "; ".join(failures))

    version = VERSION.read_text(encoding="ascii").strip()
    if manifest["constitution_version"] != version:
        raise ValueError("manifesto de producer diverge de VERSION")
    if manifest["id"] != PRODUCER_ID or manifest["version"] != PRODUCER_VERSION:
        raise ValueError("manifesto diverge da identidade da implementação")
    if manifest["runtime"]["entrypoint"] != "evolutive.provenance.declared_manifest_verifier:verify":
        raise ValueError("entrypoint do producer diverge do canônico")

    actual_digest = _implementation_sha256(PRODUCER_IMPLEMENTATION)
    pinned_digest = manifest["runtime"]["implementation_sha256"]
    if pinned_digest != actual_digest:
        raise ValueError(
            "implementation_sha256 do producer diverge: "
            f"esperado {pinned_digest}, atual {actual_digest}"
        )

    if manifest["capabilities"] != {
        "network": False,
        "subprocess": False,
        "environment": False,
        "executes_consumer_code": False,
        "observation_basis": "declared",
    }:
        raise ValueError("capabilities do producer divergem do fence canônico")

    return manifest


def attest_producer_trust(
    declaration: dict,
    authorized_artifacts: list[dict],
    evidence: dict,
    manifest_path: Path = PRODUCER_MANIFEST,
) -> dict:
    manifest = validate_producer_manifest(manifest_path)

    evidence_failures = validate_evidence(evidence)
    if evidence_failures:
        raise ValueError("evidence de provenance inválida: " + "; ".join(evidence_failures))

    if evidence["producer"] != {
        "id": manifest["id"],
        "version": manifest["version"],
        "kind": "provenance_adapter",
    }:
        raise ValueError("evidence não foi emitida pela identidade de producer esperada")

    reproduced = verify(declaration, authorized_artifacts)
    if reproduced != evidence:
        raise ValueError("evidence diverge da reprodução fresca do producer")

    attestation = {
        "attestation_version": 1,
        "constitution_version": manifest["constitution_version"],
        "subject": {"evidence_sha256": _canonical_sha256(evidence)},
        "producer": {
            "id": manifest["id"],
            "version": manifest["version"],
            "implementation_sha256": manifest["runtime"]["implementation_sha256"],
            "manifest_sha256": _canonical_sha256(manifest),
            "observation_basis": manifest["capabilities"]["observation_basis"],
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


def validate_attestation(
    attestation: dict,
    declaration: dict,
    authorized_artifacts: list[dict],
    evidence: dict,
    manifest_path: Path = PRODUCER_MANIFEST,
) -> None:
    expected = attest_producer_trust(declaration, authorized_artifacts, evidence, manifest_path)
    if attestation != expected:
        raise ValueError("attestation diverge da reprodução fresca")
