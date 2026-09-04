#!/usr/bin/env python3
"""Avalia cobertura semântica das regras sem produzir conformidade normativa positiva."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

if __package__:
    from .coverage_attestation import canonical_sha256
    from .coverage_composition import compose_coverage
    from .observation_alignment import align_observation_policy
    from .run_adapter import canonical_bytes
else:
    from coverage_attestation import canonical_sha256
    from coverage_composition import compose_coverage
    from observation_alignment import align_observation_policy
    from run_adapter import canonical_bytes

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = ROOT / "governance" / "semantic-relation-taxonomy.yaml"
PROFILES_PATH = ROOT / "governance" / "rule-semantic-profiles.yaml"
CAPABILITIES_PATH = ROOT / "governance" / "semantic-observation-capabilities.yaml"
EVALUATOR_MANIFEST = ROOT / "governance" / "semantic-coverage-evaluator.yaml"
TAXONOMY_SCHEMA = ROOT / "schema" / "semantic-relation-taxonomy.schema.json"
PROFILES_SCHEMA = ROOT / "schema" / "rule-semantic-profile.schema.json"
CAPABILITIES_SCHEMA = ROOT / "schema" / "semantic-observation-capability.schema.json"
RESULT_SCHEMA = ROOT / "schema" / "rule-semantic-coverage.schema.json"
EVALUATOR_MANIFEST_SCHEMA = ROOT / "schema" / "semantic-coverage-evaluator-manifest.schema.json"
EVALUATOR_ID = "evolutive.semantic.coverage"
EVALUATOR_VERSION = "0.1.0"

_SOURCE_PATTERN = re.compile(
    r"^(statement|scope\.(applies_to|excludes)\[([0-9]+)\]|compliance\.(pass_conditions|fail_conditions)\[([0-9]+)\])$"
)


def schema_failures(schema_path: Path, value: object) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(value))


def load_yaml_contract(path: Path, schema_path: Path, label: str) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    failures = schema_failures(schema_path, value)
    if failures:
        raise ValueError(f"{label} inválido: " + "; ".join(failures))
    return value


def validate_evaluator_authority() -> dict:
    manifest = load_yaml_contract(
        EVALUATOR_MANIFEST,
        EVALUATOR_MANIFEST_SCHEMA,
        "manifesto do semantic coverage evaluator",
    )
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    if manifest["constitution_version"] != version:
        raise ValueError("constitution_version do semantic coverage evaluator diverge da Constituição")
    if manifest["id"] != EVALUATOR_ID or manifest["version"] != EVALUATOR_VERSION:
        raise ValueError("identidade do semantic coverage evaluator diverge da implementação")
    actual = hashlib.sha256(canonical_bytes(Path(__file__))).hexdigest()
    if manifest["implementation_sha256"] != actual:
        raise ValueError(f"implementation_sha256 do semantic coverage evaluator diverge: actual={actual}")
    authority = manifest["authority"]
    if authority["semantic_coverage_only"] is not True:
        raise ValueError("semantic coverage evaluator precisa permanecer coverage-only")
    if authority["may_assert_complete_rule_semantics"] is not False:
        raise ValueError("semantic coverage evaluator v0.1.0 não pode afirmar semântica completa")
    if authority["may_produce_rule_pass"] is not False:
        raise ValueError("semantic coverage evaluator não pode produzir rule-pass")
    if authority["may_change_rule_status"] is not False:
        raise ValueError("semantic coverage evaluator não pode alterar status normativo de regra")
    return manifest


def _rule_files() -> dict[str, tuple[Path, dict]]:
    result: dict[str, tuple[Path, dict]] = {}
    for path in sorted((ROOT / "rules").glob("**/*.yaml")):
        rule = yaml.safe_load(path.read_text(encoding="utf-8"))
        rule_id = rule["id"]
        if rule_id in result:
            raise ValueError(f"rule_id duplicado ao validar semantic profiles: {rule_id}")
        result[rule_id] = (path, rule)
    return result


def _source_value(rule: dict, source: str) -> object:
    match = _SOURCE_PATTERN.fullmatch(source)
    if not match:
        raise ValueError(f"normative source inválida: {source}")
    if source == "statement":
        return rule["statement"]
    if source.startswith("scope."):
        field = match.group(2)
        index = int(match.group(3))
        values = rule["scope"][field]
    else:
        field = match.group(4)
        index = int(match.group(5))
        values = rule["compliance"][field]
    if index >= len(values):
        raise ValueError(f"normative source fora do contrato da regra: {source}")
    return values[index]


def _adapter_manifests() -> dict[tuple[str, str], dict]:
    manifests: dict[tuple[str, str], dict] = {}
    for path in sorted((ROOT / "adapters").glob("*.yaml")):
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        key = (manifest["id"], manifest["version"])
        if key in manifests:
            raise ValueError(f"manifesto de adapter duplicado: {key[0]}@{key[1]}")
        manifests[key] = manifest
    return manifests


def load_semantic_contracts() -> tuple[dict, dict, dict]:
    taxonomy = load_yaml_contract(TAXONOMY_PATH, TAXONOMY_SCHEMA, "taxonomia semântica")
    profiles = load_yaml_contract(PROFILES_PATH, PROFILES_SCHEMA, "perfis semânticos")
    capabilities = load_yaml_contract(
        CAPABILITIES_PATH,
        CAPABILITIES_SCHEMA,
        "catálogo de capabilities semânticas",
    )
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    for label, contract in (
        ("taxonomia", taxonomy),
        ("profiles", profiles),
        ("capabilities", capabilities),
    ):
        if contract["constitution_version"] != version:
            raise ValueError(f"constitution_version de {label} diverge da Constituição")

    taxonomy_ids = [item["id"] for item in taxonomy["relations"]]
    if len(taxonomy_ids) != len(set(taxonomy_ids)):
        raise ValueError("taxonomia semântica contém relation id duplicado")
    taxonomy_set = set(taxonomy_ids)

    if taxonomy["exhaustiveness"]["status"] != "not_established":
        raise ValueError("semantic coverage v0.1.0 ainda não governa taxonomia marcada como exhaustive")
    if taxonomy["exhaustiveness"].get("decision_reference") is not None:
        raise ValueError("taxonomia not_established não pode apontar decisão de exaustividade")

    rules = _rule_files()
    profile_ids: list[str] = []
    for profile in profiles["rules"]:
        rule_id = profile["rule_id"]
        profile_ids.append(rule_id)
        if rule_id not in rules:
            raise ValueError(f"semantic profile referencia regra inexistente: {rule_id}")
        _, rule = rules[rule_id]
        if canonical_sha256(rule) != profile["rule_contract_sha256"]:
            raise ValueError(f"semantic profile de {rule_id} diverge do contrato normativo atual")
        if profile["profile_exhaustiveness"]["status"] != "not_established":
            raise ValueError(f"semantic coverage v0.1.0 não aceita profile exhaustive: {rule_id}")
        if profile["profile_exhaustiveness"].get("decision_reference") is not None:
            raise ValueError(f"profile not_established não pode apontar decisão: {rule_id}")
        relation_ids = [item["relation_id"] for item in profile["relations"]]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError(f"semantic profile contém relation duplicada: {rule_id}")
        for relation in profile["relations"]:
            if relation["relation_id"] not in taxonomy_set:
                raise ValueError(
                    f"semantic profile de {rule_id} referencia relation fora da taxonomia: {relation['relation_id']}"
                )
            for source in relation["normative_sources"]:
                _source_value(rule, source)
    if len(profile_ids) != len(set(profile_ids)):
        raise ValueError("rule semantic profiles contém rule_id duplicado")

    manifests = _adapter_manifests()
    capability_keys: list[tuple[str, str]] = []
    for adapter in capabilities["adapters"]:
        key = (adapter["adapter_id"], adapter["adapter_version"])
        capability_keys.append(key)
        manifest = manifests.get(key)
        if manifest is None:
            raise ValueError(f"capability semântica referencia adapter inexistente: {key[0]}@{key[1]}")
        if manifest["runtime"]["implementation_sha256"] != adapter["adapter_implementation_sha256"]:
            raise ValueError(f"capability semântica diverge do implementation digest: {key[0]}@{key[1]}")
        relation_ids = [item["relation_id"] for item in adapter["relations"]]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError(f"capability semântica contém relation duplicada: {key[0]}@{key[1]}")
        for relation in adapter["relations"]:
            if relation["relation_id"] not in taxonomy_set:
                raise ValueError(
                    f"capability de {key[0]} referencia relation fora da taxonomia: {relation['relation_id']}"
                )
    if len(capability_keys) != len(set(capability_keys)):
        raise ValueError("catálogo de capabilities contém adapter duplicado")

    return taxonomy, profiles, capabilities


def assess_rule_semantic_coverage(config_path: Path, project_root: Path) -> dict:
    evaluator = validate_evaluator_authority()
    taxonomy, profiles, capabilities = load_semantic_contracts()
    alignment = align_observation_policy(config_path, project_root)
    composition = compose_coverage(config_path, project_root)

    if alignment["subject"]["inventory_sha256"] != composition["subject"]["inventory_sha256"]:
        raise ValueError("alignment e coverage composition pertencem a inventários diferentes")
    if alignment["subject"]["observation_policy_sha256"] != composition["subject"]["observation_policy_sha256"]:
        raise ValueError("alignment e coverage composition pertencem a observation policies diferentes")

    capability_map: dict[tuple[str, str], dict[str, dict]] = {}
    for adapter in capabilities["adapters"]:
        key = (adapter["adapter_id"], adapter["adapter_version"])
        capability_map[key] = {item["relation_id"]: item for item in adapter["relations"]}

    composition_rows = composition["evaluation"]["observations"]
    rules_output: list[dict] = []
    for profile in profiles["rules"]:
        relation_rows: list[dict] = []
        required_uncovered = False
        required_partial = False
        any_observed = False

        for relation in profile["relations"]:
            observations: list[dict] = []
            complete_observers = 0
            for observation in composition_rows:
                key = (observation["adapter_id"], observation["adapter_version"])
                capability = capability_map.get(key, {}).get(relation["relation_id"])
                if capability is None:
                    continue
                any_observed = True
                observations.append({
                    "adapter_id": observation["adapter_id"],
                    "adapter_version": observation["adapter_version"],
                    "coverage_verdict": observation["coverage_verdict"],
                    "assurance": capability["assurance"],
                })
                if (
                    observation["coverage_verdict"] == "sufficient"
                    and capability["assurance"] == "complete_when_coverage_sufficient"
                ):
                    complete_observers += 1

            if composition_rows and complete_observers == len(composition_rows):
                status = "covered"
            elif observations:
                status = "partial"
            else:
                status = "uncovered"

            if relation["required"] and status == "uncovered":
                required_uncovered = True
            if relation["required"] and status == "partial":
                required_partial = True

            relation_rows.append({
                "relation_id": relation["relation_id"],
                "required": relation["required"],
                "status": status,
                "observations": observations,
            })

        reasons: list[str] = []
        if taxonomy["exhaustiveness"]["status"] != "established":
            reasons.append("taxonomy_not_exhaustive")
        if profile["profile_exhaustiveness"]["status"] != "established":
            reasons.append("profile_not_exhaustive")
        if alignment["evaluation"]["verdict"] != "aligned":
            reasons.append("alignment_incomplete")
        if composition["evaluation"]["verdict"] != "complete":
            reasons.append("coverage_incomplete")
        if alignment["evaluation"]["unclassified_files"]["count"] != 0:
            reasons.append("unclassified_files_present")
        if required_uncovered:
            reasons.append("required_relation_uncovered")
        if required_partial:
            reasons.append("required_relation_partial")
        reasons.append("complete_semantics_not_authorized")

        rules_output.append({
            "rule_id": profile["rule_id"],
            "verdict": "partial" if any_observed else "not_proven",
            "taxonomy_exhaustiveness": taxonomy["exhaustiveness"]["status"],
            "profile_exhaustiveness": profile["profile_exhaustiveness"]["status"],
            "complete_rule_semantics": False,
            "relations": relation_rows,
            "reasons": reasons,
        })

    result = {
        "assessment_version": 1,
        "constitution_version": taxonomy["constitution_version"],
        "subject": {
            "inventory_sha256": composition["subject"]["inventory_sha256"],
            "observation_policy_sha256": composition["subject"]["observation_policy_sha256"],
            "taxonomy_sha256": canonical_sha256(taxonomy),
            "profiles_sha256": canonical_sha256(profiles),
            "capabilities_sha256": canonical_sha256(capabilities),
        },
        "evidence": {
            "alignment_sha256": canonical_sha256(alignment),
            "composition_sha256": canonical_sha256(composition),
        },
        "evaluator": {
            "id": evaluator["id"],
            "version": evaluator["version"],
            "implementation_sha256": evaluator["implementation_sha256"],
        },
        "rules": rules_output,
    }
    failures = schema_failures(RESULT_SCHEMA, result)
    if failures:
        raise ValueError("semantic coverage assessment inválida: " + "; ".join(failures))
    return result


def validate_semantic_coverage(
    assessment: dict,
    config_path: Path,
    project_root: Path,
) -> list[str]:
    failures = schema_failures(RESULT_SCHEMA, assessment)
    if failures:
        return failures
    try:
        expected = assess_rule_semantic_coverage(config_path, project_root)
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    if assessment != expected:
        return ["semantic coverage assessment diverge da recomputação determinística do snapshot atual"]
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
            failures = validate_semantic_coverage(existing, args.config, args.project_root)
            if failures:
                raise ValueError("; ".join(failures))
            print("OK: semantic coverage assessment corresponde ao snapshot atual.")
            return 0
        result = assess_rule_semantic_coverage(args.config, args.project_root)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(f"Falha na avaliação de semantic coverage: {exc}", file=sys.stderr)
        return 1
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
