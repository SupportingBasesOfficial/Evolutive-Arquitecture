#!/usr/bin/env python3
"""Deriva resultados de conformidade a partir de evidências frescas e autoridades separadas."""

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
    from .coverage_composition import compose_coverage
    from .generate_architecture_evidence import generate_architecture_evidence
    from .observation_alignment import align_observation_policy
    from .observation_policy import load_observation_policy, resolve_required_manifests
    from .run_adapter import canonical_bytes
    from .run_checker import execute_checker
else:
    from coverage_attestation import attest_coverage, canonical_sha256
    from coverage_composition import compose_coverage
    from generate_architecture_evidence import generate_architecture_evidence
    from observation_alignment import align_observation_policy
    from observation_policy import load_observation_policy, resolve_required_manifests
    from run_adapter import canonical_bytes
    from run_checker import execute_checker

ROOT = Path(__file__).resolve().parents[1]
RESULT_SCHEMA = ROOT / "schema" / "aggregated-conformance-result.schema.json"
POLICY_SCHEMA = ROOT / "schema" / "positive-result-policy.schema.json"
POLICY_PATH = ROOT / "governance" / "positive-result-policy.yaml"
AGGREGATOR_MANIFEST_SCHEMA = ROOT / "schema" / "result-aggregator-manifest.schema.json"
AGGREGATOR_MANIFEST = ROOT / "governance" / "result-aggregator.yaml"
CHECKER_MANIFEST = ROOT / "checkers" / "architecture.yaml"
AGGREGATOR_ID = "evolutive.result.aggregator"
AGGREGATOR_VERSION = "0.1.0"


def schema_failures(schema_path: Path, value: object) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(value))


def load_positive_policy() -> dict:
    policy = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    failures = schema_failures(POLICY_SCHEMA, policy)
    if failures:
        raise ValueError("positive result policy inválida: " + "; ".join(failures))
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    if policy["constitution_version"] != version:
        raise ValueError("constitution_version da positive result policy diverge da Constituição")
    ids = [item["rule_id"] for item in policy["rules"]]
    if len(ids) != len(set(ids)):
        raise ValueError("positive result policy contém rule_id duplicado")
    return policy


def validate_aggregator_authority() -> dict:
    manifest = yaml.safe_load(AGGREGATOR_MANIFEST.read_text(encoding="utf-8"))
    failures = schema_failures(AGGREGATOR_MANIFEST_SCHEMA, manifest)
    if failures:
        raise ValueError("manifesto do result aggregator inválido: " + "; ".join(failures))
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    if manifest["constitution_version"] != version:
        raise ValueError("constitution_version do result aggregator diverge da Constituição")
    if manifest["id"] != AGGREGATOR_ID or manifest["version"] != AGGREGATOR_VERSION:
        raise ValueError("identidade do result aggregator diverge da implementação")
    actual = hashlib.sha256(canonical_bytes(Path(__file__))).hexdigest()
    if manifest["implementation_sha256"] != actual:
        raise ValueError(f"implementation_sha256 do result aggregator diverge: actual={actual}")
    authority = manifest["authority"]
    if authority["may_mutate_checker_result"] is not False:
        raise ValueError("result aggregator não pode mutar checker result")
    if authority["may_change_rule_status"] is not False:
        raise ValueError("result aggregator não pode alterar status normativo de regra")
    return manifest


def checker_manifest_data() -> dict:
    return yaml.safe_load(CHECKER_MANIFEST.read_text(encoding="utf-8"))


def aggregate_results(config_path: Path, project_root: Path) -> dict:
    aggregator = validate_aggregator_authority()
    positive_policy = load_positive_policy()
    observation_policy = load_observation_policy(config_path, project_root)
    alignment = align_observation_policy(config_path, project_root)
    composition = compose_coverage(config_path, project_root)

    if alignment["subject"]["inventory_sha256"] != composition["subject"]["inventory_sha256"]:
        raise ValueError("alignment e coverage composition pertencem a inventários diferentes")
    if alignment["subject"]["observation_policy_sha256"] != composition["subject"]["observation_policy_sha256"]:
        raise ValueError("alignment e coverage composition pertencem a observation policies diferentes")

    checker_manifest = checker_manifest_data()
    profiles = {item["rule_id"]: item for item in positive_policy["rules"]}
    for profile in profiles.values():
        if profile["checker"]["id"] != checker_manifest["id"] or profile["checker"]["version"] != checker_manifest["version"]:
            raise ValueError(f"positive profile de {profile['rule_id']} diverge do checker canônico")
        if profile["rule_id"] not in checker_manifest["rules"]:
            raise ValueError(f"positive profile referencia regra não concedida ao checker: {profile['rule_id']}")

    manifests = resolve_required_manifests(observation_policy)
    observations_by_rule: dict[str, list[dict]] = {rule_id: [] for rule_id in checker_manifest["rules"]}

    for adapter_manifest_path in manifests:
        adapter_manifest = yaml.safe_load(adapter_manifest_path.read_text(encoding="utf-8"))
        evidence = generate_architecture_evidence(config_path, project_root, adapter_manifest_path)
        attestation = attest_coverage(evidence, config_path, project_root, adapter_manifest_path)
        if attestation["subject"]["inventory_sha256"] != composition["subject"]["inventory_sha256"]:
            raise ValueError("attestation fresca diverge do inventário composto")

        request = {
            "request_version": 1,
            "checker_id": checker_manifest["id"],
            "rule_ids": list(checker_manifest["rules"]),
            "files": [],
            "architecture_graph": evidence["graph"],
        }
        checker_result = execute_checker(CHECKER_MANIFEST, request)
        if checker_result["errors"]:
            raise ValueError("checker retornou erros durante agregação")

        for outcome in checker_result["outcomes"]:
            if outcome["status"] not in {"fail", "unknown"}:
                raise ValueError(
                    f"aggregator 0.1.0 aceita apenas checker fail/unknown, recebeu {outcome['status']}"
                )
            observations_by_rule[outcome["rule_id"]].append({
                "adapter_id": adapter_manifest["id"],
                "adapter_version": adapter_manifest["version"],
                "checker_status": outcome["status"],
                "findings_count": len(outcome["findings"]),
                "findings_sha256": canonical_sha256(outcome["findings"]),
                "attestation_sha256": canonical_sha256(attestation),
            })

    final_outcomes: list[dict] = []
    for rule_id in checker_manifest["rules"]:
        rows = observations_by_rule[rule_id]
        if any(row["checker_status"] == "fail" for row in rows):
            status = "fail"
            basis = "checker_fail"
            reasons: list[str] = []
        else:
            profile = profiles.get(rule_id)
            if profile is None:
                status = "unknown"
                basis = "no_positive_profile"
                reasons = ["positive_profile_missing"]
            else:
                reasons = []
                requirements = profile["positive_derivation"]
                if requirements["require_alignment"] and alignment["evaluation"]["verdict"] != "aligned":
                    reasons.append("alignment_incomplete")
                if requirements["require_complete_coverage"] and composition["evaluation"]["verdict"] != "complete":
                    reasons.append("coverage_incomplete")
                if requirements["require_zero_unclassified_files"] and alignment["evaluation"]["unclassified_files"]["count"] != 0:
                    reasons.append("unclassified_files_present")
                if any(row["checker_status"] != requirements["source_status"] for row in rows):
                    reasons.append("checker_not_unknown")
                if reasons:
                    status = "unknown"
                    basis = "insufficient_positive_evidence"
                else:
                    status = "pass"
                    basis = "positive_derivation"

        final_outcomes.append({
            "rule_id": rule_id,
            "status": status,
            "basis": basis,
            "checker_observations": rows,
            "reasons": reasons,
        })

    result = {
        "aggregation_version": 1,
        "constitution_version": observation_policy["constitution_version"],
        "subject": {
            "inventory_sha256": composition["subject"]["inventory_sha256"],
            "catalog_sha256": alignment["subject"]["catalog_sha256"],
            "observation_policy_sha256": composition["subject"]["observation_policy_sha256"],
            "positive_result_policy_sha256": canonical_sha256(positive_policy),
        },
        "evaluator": {
            "id": aggregator["id"],
            "version": aggregator["version"],
            "implementation_sha256": aggregator["implementation_sha256"],
        },
        "evidence": {
            "alignment_sha256": canonical_sha256(alignment),
            "composition_sha256": canonical_sha256(composition),
        },
        "outcomes": final_outcomes,
    }
    failures = schema_failures(RESULT_SCHEMA, result)
    if failures:
        raise ValueError("resultado agregado inválido: " + "; ".join(failures))
    return result


def validate_aggregated_result(result: dict, config_path: Path, project_root: Path) -> list[str]:
    failures = schema_failures(RESULT_SCHEMA, result)
    if failures:
        return failures
    try:
        expected = aggregate_results(config_path, project_root)
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    if result != expected:
        return ["resultado agregado diverge da recomputação determinística do snapshot atual"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--validate", type=Path)
    args = parser.parse_args()
    try:
        if args.validate:
            existing = yaml.safe_load(args.validate.read_text(encoding="utf-8"))
            failures = validate_aggregated_result(existing, args.config, args.project_root)
            if failures:
                raise ValueError("; ".join(failures))
            print("OK: aggregated conformance result corresponde ao snapshot atual.")
            return 0
        result = aggregate_results(args.config, args.project_root)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(f"Falha na agregação de resultados: {exc}", file=sys.stderr)
        return 1
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
