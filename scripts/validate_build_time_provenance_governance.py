#!/usr/bin/env python3
"""Valida taxonomia, mapeamento semântico e evidence de provenance de build-time."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "VERSION"
PROVENANCE_TAXONOMY = ROOT / "governance" / "build-time-provenance-taxonomy.yaml"
SEMANTIC_MAPPING = ROOT / "governance" / "build-time-semantic-mapping.yaml"
SEMANTIC_TAXONOMY = ROOT / "governance" / "semantic-relation-taxonomy.yaml"
TAXONOMY_SCHEMA = ROOT / "schema" / "build-time-provenance-taxonomy.schema.json"
MAPPING_SCHEMA = ROOT / "schema" / "build-time-semantic-mapping.schema.json"
EVIDENCE_SCHEMA = ROOT / "schema" / "build-time-provenance-evidence.schema.json"
EVIDENCE_TEMPLATE = ROOT / "templates" / "build-time-provenance-evidence.yaml"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _schema_failures(value: object, schema_path: Path) -> list[str]:
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(value))


def validate_evidence(
    evidence: dict,
    provenance: dict | None = None,
    mapping: dict | None = None,
    version: str | None = None,
) -> list[str]:
    """Valida um documento de provenance evidence contra as autoridades canônicas."""

    try:
        provenance = provenance or _load_yaml(PROVENANCE_TAXONOMY)
        mapping = mapping or _load_yaml(SEMANTIC_MAPPING)
        version = version or VERSION.read_text(encoding="ascii").strip()
        evidence_schema = _load_json(EVIDENCE_SCHEMA)
        Draft202012Validator.check_schema(evidence_schema)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return [str(exc)]

    failures = sorted(
        f"schema: {error.message}"
        for error in Draft202012Validator(evidence_schema).iter_errors(evidence)
    )
    if failures:
        return failures

    if evidence["constitution_version"] != version:
        failures.append("constitution_version diverge de VERSION")

    class_ids = {item["id"] for item in provenance["classes"]}
    mapping_by_class = {item["provenance_class"]: item for item in mapping["mappings"]}

    transformation_ids = [item["id"] for item in evidence["transformations"]]
    if len(transformation_ids) != len(set(transformation_ids)):
        failures.append("transformation ids precisam ser únicos")

    artifact_bindings: dict[str, tuple[str, str]] = {}

    for item in evidence["transformations"]:
        provenance_class = item["provenance_class"]
        if provenance_class not in class_ids:
            failures.append(
                f"{item['id']}: provenance_class desconhecida: {provenance_class}"
            )
            continue

        mapping_entry = mapping_by_class.get(provenance_class)
        if mapping_entry is None:
            failures.append(
                f"{item['id']}: provenance_class sem mapping canônico: {provenance_class}"
            )
            continue

        candidates = set(item["candidate_relations"])
        allowed = set(mapping_entry["candidate_relations"])
        extra = sorted(candidates - allowed)
        if extra:
            failures.append(
                f"{item['id']}: candidate_relations fora do mapping: " + ", ".join(extra)
            )

        for direction in ("inputs", "outputs"):
            for artifact in item[direction]:
                identity = artifact["identity"]
                binding = (artifact["kind"], artifact["sha256"])
                previous = artifact_bindings.get(identity)
                if previous is None:
                    artifact_bindings[identity] = binding
                elif previous != binding:
                    failures.append(
                        f"{item['id']}: artifact identity {identity!r} possui binding conflitante"
                    )

    return sorted(failures)


def validate_contracts() -> list[str]:
    try:
        version = VERSION.read_text(encoding="ascii").strip()
        provenance = _load_yaml(PROVENANCE_TAXONOMY)
        mapping = _load_yaml(SEMANTIC_MAPPING)
        semantic = _load_yaml(SEMANTIC_TAXONOMY)
        evidence = _load_yaml(EVIDENCE_TEMPLATE)
        evidence_schema = _load_json(EVIDENCE_SCHEMA)
        Draft202012Validator.check_schema(evidence_schema)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return [str(exc)]

    failures: list[str] = []
    failures.extend(f"provenance taxonomy: {item}" for item in _schema_failures(provenance, TAXONOMY_SCHEMA))
    failures.extend(f"semantic mapping: {item}" for item in _schema_failures(mapping, MAPPING_SCHEMA))
    if failures:
        return sorted(failures)

    for label, value in (("provenance taxonomy", provenance), ("semantic mapping", mapping)):
        if value["constitution_version"] != version:
            failures.append(f"{label}: constitution_version diverge de VERSION")

    class_ids = [item["id"] for item in provenance["classes"]]
    if len(class_ids) != len(set(class_ids)):
        failures.append("provenance taxonomy: class ids precisam ser únicos")

    relation_ids = {item["id"] for item in semantic["relations"]}
    mappings = mapping["mappings"]
    mapped_classes = [item["provenance_class"] for item in mappings]
    if len(mapped_classes) != len(set(mapped_classes)):
        failures.append("semantic mapping: provenance_class precisa aparecer uma única vez")

    missing_mappings = sorted(set(class_ids) - set(mapped_classes))
    extra_mappings = sorted(set(mapped_classes) - set(class_ids))
    if missing_mappings:
        failures.append("semantic mapping: faltam classes: " + ", ".join(missing_mappings))
    if extra_mappings:
        failures.append("semantic mapping: classes desconhecidas: " + ", ".join(extra_mappings))

    for item in mappings:
        unknown = sorted(set(item["candidate_relations"]) - relation_ids)
        if unknown:
            failures.append(
                f"semantic mapping {item['provenance_class']}: relations desconhecidas: "
                + ", ".join(unknown)
            )
        if item["completeness"] != "partial":
            failures.append(
                f"semantic mapping {item['provenance_class']}: completeness precisa permanecer partial nesta versão"
            )

    failures.extend(
        f"provenance evidence template: {item}"
        for item in validate_evidence(evidence, provenance=provenance, mapping=mapping, version=version)
    )

    if provenance["authority"] != {
        "provenance_only": True,
        "may_define_semantic_relation": False,
        "may_assert_semantic_exhaustiveness": False,
    }:
        failures.append("provenance taxonomy: authority diverge do fence canônico")

    if mapping["authority"] != {
        "advisory_mapping_only": True,
        "may_create_semantic_relation": False,
        "may_assert_semantic_exhaustiveness": False,
    }:
        failures.append("semantic mapping: authority diverge do fence canônico")

    return sorted(failures)


def main() -> int:
    failures = validate_contracts()
    if failures:
        for failure in failures:
            print(f"ERRO: {failure}", file=sys.stderr)
        return 1
    print("OK: governança de build-time provenance válida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
