#!/usr/bin/env python3
"""Avalia suficiência de coverage sem alterar resultados do checker universal."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

if __package__:
    from .generate_architecture_evidence import generate_architecture_evidence
    from .run_adapter import canonical_bytes
    from .validate_adapter_contract import validate_manifest
else:
    from generate_architecture_evidence import generate_architecture_evidence
    from run_adapter import canonical_bytes
    from validate_adapter_contract import validate_manifest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_SCHEMA = ROOT / "schema" / "architecture-evidence.schema.json"
ATTESTATION_SCHEMA = ROOT / "schema" / "coverage-attestation.schema.json"
ATTESTOR_ID = "evolutive.coverage.attestor"
ATTESTOR_VERSION = "0.1.0"


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def schema_failures(schema_path: Path, value: object) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(value))


def validate_fresh_evidence(
    evidence: dict,
    config_path: Path,
    project_root: Path,
    manifest_path: Path,
) -> dict:
    evidence_failures = schema_failures(EVIDENCE_SCHEMA, evidence)
    if evidence_failures:
        raise ValueError("evidência inválida: " + "; ".join(evidence_failures))
    if evidence["producer"]["kind"] != "adapter":
        raise ValueError("coverage attestation exige evidência produzida por adapter")

    manifest_failures = validate_manifest(manifest_path)
    if manifest_failures:
        raise ValueError("manifesto inválido: " + "; ".join(manifest_failures))
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    observation = evidence["observation"]

    if manifest["id"] != evidence["producer"]["id"]:
        raise ValueError("manifesto não corresponde ao producer da evidência")
    if manifest["version"] != evidence["producer"]["version"]:
        raise ValueError("versão do manifesto diverge da evidência")
    if manifest["ecosystem"] != observation["ecosystem"]:
        raise ValueError("ecossistema do manifesto diverge da evidência")
    if manifest["constitution_version"] != evidence["constitution_version"]:
        raise ValueError("versão constitucional do manifesto diverge da evidência")

    expected = generate_architecture_evidence(config_path, project_root, manifest_path)
    if evidence != expected:
        raise ValueError("evidência diverge da execução fresca policy -> broker -> adapter -> evidence")

    audit = observation["broker_audit"]
    if audit["files_considered"] != audit["files_delivered"] + len(audit["skipped"]):
        raise ValueError("broker_audit não fecha files_considered = delivered + skipped")

    accepted = set(manifest["capabilities"]["file_extensions"])
    for item in audit["skipped"]:
        if item["reason"] == "extension_not_allowed" and Path(item["path"]).suffix in accepted:
            raise ValueError("arquivo suportado foi marcado como extension_not_allowed")
    return manifest


def attest_coverage(
    evidence: dict,
    config_path: Path,
    project_root: Path,
    manifest_path: Path,
) -> dict:
    manifest = validate_fresh_evidence(evidence, config_path, project_root, manifest_path)
    observation = evidence["observation"]
    coverage = observation["coverage"]
    audit = observation["broker_audit"]

    no_inventory_gaps = not audit["missing_roots"] and not audit["skipped_symlinks"]
    relevant_skips = [item for item in audit["skipped"] if item["reason"] != "extension_not_allowed"]
    no_relevant_broker_skips = not relevant_skips
    all_delivered_files_analyzed = coverage["files_received"] == coverage["files_parsed"]
    no_observation_errors = not observation["errors"]
    no_unresolved_references = coverage["unresolved_references"] == 0

    criteria = {
        "no_inventory_gaps": no_inventory_gaps,
        "no_relevant_broker_skips": no_relevant_broker_skips,
        "all_delivered_files_analyzed": all_delivered_files_analyzed,
        "no_observation_errors": no_observation_errors,
        "no_unresolved_references": no_unresolved_references,
    }
    reason_by_criterion = {
        "no_inventory_gaps": "inventory_gap",
        "no_relevant_broker_skips": "relevant_broker_skip",
        "all_delivered_files_analyzed": "files_not_analyzed",
        "no_observation_errors": "observation_error",
        "no_unresolved_references": "unresolved_reference",
    }
    reasons = [reason_by_criterion[name] for name, satisfied in criteria.items() if not satisfied]

    attestation = {
        "attestation_version": 1,
        "constitution_version": evidence["constitution_version"],
        "subject": {
            "evidence_sha256": canonical_sha256(evidence),
            "inventory_sha256": audit["inventory_sha256"],
            "delivered_content_sha256": audit["delivered_content_sha256"],
        },
        "scope": {
            "ecosystem": observation["ecosystem"],
            "adapter_id": evidence["producer"]["id"],
            "adapter_version": evidence["producer"]["version"],
            "adapter_implementation_sha256": manifest["runtime"]["implementation_sha256"],
            "file_extensions": list(manifest["capabilities"]["file_extensions"]),
        },
        "evaluator": {
            "id": ATTESTOR_ID,
            "version": ATTESTOR_VERSION,
            "implementation_sha256": hashlib.sha256(canonical_bytes(Path(__file__))).hexdigest(),
        },
        "evaluation": {
            "verdict": "sufficient" if all(criteria.values()) else "insufficient",
            "criteria": criteria,
            "reasons": reasons,
        },
    }
    failures = schema_failures(ATTESTATION_SCHEMA, attestation)
    if failures:
        raise ValueError("attestation gerada é inválida: " + "; ".join(failures))
    return attestation


def validate_attestation(
    attestation: dict,
    evidence: dict,
    config_path: Path,
    project_root: Path,
    manifest_path: Path,
) -> list[str]:
    failures = schema_failures(ATTESTATION_SCHEMA, attestation)
    if failures:
        return failures
    try:
        expected = attest_coverage(evidence, config_path, project_root, manifest_path)
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    if attestation != expected:
        return ["attestation diverge da avaliação determinística da evidência atual"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--validate", type=Path, help="attestation YAML existente a validar")
    args = parser.parse_args()
    try:
        evidence = yaml.safe_load(args.evidence.read_text(encoding="utf-8"))
        if args.validate:
            existing = yaml.safe_load(args.validate.read_text(encoding="utf-8"))
            failures = validate_attestation(
                existing, evidence, args.config, args.project_root, args.manifest
            )
            if failures:
                raise ValueError("; ".join(failures))
            print("OK: coverage attestation corresponde ao snapshot e à evidência atuais.")
            return 0
        attestation = attest_coverage(evidence, args.config, args.project_root, args.manifest)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(f"Falha na coverage attestation: {exc}", file=sys.stderr)
        return 1
    print(yaml.safe_dump(attestation, allow_unicode=True, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
