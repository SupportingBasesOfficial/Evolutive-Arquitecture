#!/usr/bin/env python3
"""Compõe coverage attestations exigidas por observation policy sem alterar outcomes de regra."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

if __package__:
    from .coverage_attestation import attest_coverage, canonical_sha256
    from .generate_architecture_evidence import generate_architecture_evidence
    from .observation_policy import load_observation_policy, resolve_required_manifests
    from .run_adapter import canonical_bytes
else:
    from coverage_attestation import attest_coverage, canonical_sha256
    from generate_architecture_evidence import generate_architecture_evidence
    from observation_policy import load_observation_policy, resolve_required_manifests
    from run_adapter import canonical_bytes

ROOT = Path(__file__).resolve().parents[1]
COMPOSITION_SCHEMA = ROOT / "schema" / "coverage-composition.schema.json"
COMPOSER_MANIFEST_SCHEMA = ROOT / "schema" / "coverage-composer-manifest.schema.json"
COMPOSER_MANIFEST = ROOT / "governance" / "coverage-composer.yaml"
COMPOSER_ID = "evolutive.coverage.composer"
COMPOSER_VERSION = "0.1.0"


def schema_failures(schema_path: Path, value: object) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(value))


def validate_composer_authority() -> dict:
    manifest = yaml.safe_load(COMPOSER_MANIFEST.read_text(encoding="utf-8"))
    failures = schema_failures(COMPOSER_MANIFEST_SCHEMA, manifest)
    if failures:
        raise ValueError("manifesto do coverage composer inválido: " + "; ".join(failures))
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    if manifest["constitution_version"] != version:
        raise ValueError("constitution_version do coverage composer diverge da Constituição")
    if manifest["id"] != COMPOSER_ID or manifest["version"] != COMPOSER_VERSION:
        raise ValueError("identidade do coverage composer diverge da implementação")
    actual = hashlib.sha256(canonical_bytes(Path(__file__))).hexdigest()
    if manifest["implementation_sha256"] != actual:
        raise ValueError(f"implementation_sha256 do coverage composer diverge: actual={actual}")
    if manifest["authority"]["may_change_checker_outcome"] is not False:
        raise ValueError("coverage composer não pode alterar outcome do checker")
    if manifest["authority"]["ecosystem_discovery"] is not False:
        raise ValueError("coverage composer 0.1.0 não possui autoridade de ecosystem discovery")
    return manifest


def compose_coverage(config_path: Path, project_root: Path) -> dict:
    composer_manifest = validate_composer_authority()
    policy = load_observation_policy(config_path, project_root)
    manifest_paths = resolve_required_manifests(policy)

    observation_rows: list[dict] = []
    required_scope: list[dict] = []
    inventory_sha256: str | None = None
    sufficient_count = 0

    for manifest_path in manifest_paths:
        adapter_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        evidence = generate_architecture_evidence(config_path, project_root, manifest_path)
        attestation = attest_coverage(evidence, config_path, project_root, manifest_path)
        current_inventory = attestation["subject"]["inventory_sha256"]
        if inventory_sha256 is None:
            inventory_sha256 = current_inventory
        elif inventory_sha256 != current_inventory:
            raise ValueError("attestations obrigatórias não pertencem ao mesmo inventário autorizado")

        coverage_verdict = attestation["evaluation"]["verdict"]
        if coverage_verdict == "sufficient":
            sufficient_count += 1

        required_scope.append({
            "adapter_id": adapter_manifest["id"],
            "adapter_version": adapter_manifest["version"],
            "ecosystem": adapter_manifest["ecosystem"],
            "adapter_implementation_sha256": adapter_manifest["runtime"]["implementation_sha256"],
        })
        observation_rows.append({
            "adapter_id": adapter_manifest["id"],
            "adapter_version": adapter_manifest["version"],
            "ecosystem": adapter_manifest["ecosystem"],
            "attestation_sha256": canonical_sha256(attestation),
            "coverage_verdict": coverage_verdict,
        })

    if inventory_sha256 is None:
        raise ValueError("observation policy não produziu observações obrigatórias")

    required_count = len(observation_rows)
    complete = sufficient_count == required_count
    composition = {
        "composition_version": 1,
        "constitution_version": policy["constitution_version"],
        "subject": {
            "observation_policy_sha256": canonical_sha256(policy),
            "inventory_sha256": inventory_sha256,
        },
        "scope": {
            "basis": "declared_observation_policy",
            "required_observations": required_scope,
        },
        "evaluator": {
            "id": composer_manifest["id"],
            "version": composer_manifest["version"],
            "implementation_sha256": composer_manifest["implementation_sha256"],
        },
        "evaluation": {
            "verdict": "complete" if complete else "incomplete",
            "required_count": required_count,
            "sufficient_count": sufficient_count,
            "observations": observation_rows,
            "reasons": [] if complete else ["required_observation_insufficient"],
        },
    }
    failures = schema_failures(COMPOSITION_SCHEMA, composition)
    if failures:
        raise ValueError("coverage composition gerada é inválida: " + "; ".join(failures))
    return composition


def validate_composition(
    composition: dict,
    config_path: Path,
    project_root: Path,
) -> list[str]:
    failures = schema_failures(COMPOSITION_SCHEMA, composition)
    if failures:
        return failures
    try:
        expected = compose_coverage(config_path, project_root)
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    if composition != expected:
        return ["coverage composition diverge da composição determinística do snapshot atual"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--validate", type=Path, help="coverage composition YAML existente a validar")
    args = parser.parse_args()
    try:
        if args.validate:
            existing = yaml.safe_load(args.validate.read_text(encoding="utf-8"))
            failures = validate_composition(existing, args.config, args.project_root)
            if failures:
                raise ValueError("; ".join(failures))
            print("OK: coverage composition corresponde à policy e ao snapshot atuais.")
            return 0
        composition = compose_coverage(args.config, args.project_root)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(f"Falha na coverage composition: {exc}", file=sys.stderr)
        return 1
    print(yaml.safe_dump(composition, allow_unicode=True, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
