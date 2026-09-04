#!/usr/bin/env python3
"""Valida decisões e vínculos de exaustividade semântica de forma fail-closed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

if __package__:
    from .coverage_attestation import canonical_sha256
else:
    from coverage_attestation import canonical_sha256

ROOT = Path(__file__).resolve().parents[1]
DECISION_SCHEMA = ROOT / "schema" / "semantic-exhaustiveness-decision.schema.json"
TAXONOMY_SCHEMA = ROOT / "schema" / "semantic-relation-taxonomy.schema.json"
PROFILE_SCHEMA = ROOT / "schema" / "rule-semantic-profile.schema.json"
TAXONOMY_PATH = ROOT / "governance" / "semantic-relation-taxonomy.yaml"
PROFILES_PATH = ROOT / "governance" / "rule-semantic-profiles.yaml"
DECISIONS_ROOT = ROOT / "decisions" / "semantic-exhaustiveness"
TAXONOMY_ID = "semantic-relation-taxonomy"


def schema_failures(schema_path: Path, value: object) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(value))


def taxonomy_snapshot(taxonomy: dict) -> dict:
    return {
        "taxonomy_version": taxonomy["taxonomy_version"],
        "constitution_version": taxonomy["constitution_version"],
        "relations": taxonomy["relations"],
    }


def profile_snapshot(document: dict, profile: dict) -> dict:
    return {
        "profile_version": document["profile_version"],
        "constitution_version": document["constitution_version"],
        "rule_id": profile["rule_id"],
        "rule_contract_sha256": profile["rule_contract_sha256"],
        "relations": profile["relations"],
    }


def expected_decision_path(record: dict) -> str:
    subject = record["subject"]
    digest = subject["semantic_content_sha256"]
    outcome = record["decision"]["outcome"]
    if subject["kind"] == "taxonomy":
        return f"decisions/semantic-exhaustiveness/taxonomy/{digest}-{outcome}.yaml"
    return (
        "decisions/semantic-exhaustiveness/rules/"
        f"{subject['id']}/{digest}-{outcome}.yaml"
    )


def validate_decision_record(record: dict, relative_path: str) -> list[str]:
    failures = schema_failures(DECISION_SCHEMA, record)
    if failures:
        return failures

    subject = record["subject"]
    snapshot = record["snapshot"]
    if snapshot["constitution_version"] != record["constitution_version"]:
        failures.append("snapshot e decisão possuem constitution_version diferentes")

    if subject["kind"] == "taxonomy":
        if subject["id"] != TAXONOMY_ID:
            failures.append("subject taxonomy precisa usar id semantic-relation-taxonomy")
        if "taxonomy_version" not in snapshot:
            failures.append("decisão taxonomy precisa carregar taxonomy snapshot")
    else:
        if "profile_version" not in snapshot:
            failures.append("decisão rule_profile precisa carregar profile snapshot")
        elif subject["id"] != snapshot.get("rule_id"):
            failures.append("subject rule_profile diverge do rule_id do snapshot")

    actual_digest = canonical_sha256(snapshot)
    if subject["semantic_content_sha256"] != actual_digest:
        failures.append(
            "semantic_content_sha256 da decisão diverge do snapshot: "
            f"actual={actual_digest}"
        )

    expected = expected_decision_path(record)
    if relative_path != expected:
        failures.append(f"caminho canônico da decisão inválido: esperado {expected}")

    review = record["review"]
    outcome = record["decision"]["outcome"]
    if outcome == "approved":
        false_dimensions = [
            name for name, value in review["dimensions"].items() if value is not True
        ]
        if false_dimensions:
            failures.append(
                "decisão approved exige todas as dimensões revisadas: "
                + ", ".join(sorted(false_dimensions))
            )
        if review["counterexample_search"]["performed"] is not True:
            failures.append("decisão approved exige busca adversarial por contraexemplos")
        if len(review["counterexample_search"]["methods"]) < 2:
            failures.append("decisão approved exige ao menos dois métodos de busca por contraexemplos")
        if review["unresolved_gaps"]:
            failures.append("decisão approved não pode possuir unresolved_gaps")
        if any(
            case["disposition"] == "unresolved"
            for case in review["counterexample_search"]["cases"]
        ):
            failures.append("decisão approved não pode preservar contraexemplo unresolved")
        evidence_kinds = {item["kind"] for item in review["evidence"]}
        if len(evidence_kinds) < 2:
            failures.append("decisão approved exige ao menos duas classes distintas de evidência")
        references = [item["reference"] for item in review["evidence"]]
        if len(references) != len(set(references)):
            failures.append("decisão approved não pode duplicar referência de evidência")

    supersedes = record.get("supersedes")
    if supersedes is not None:
        if not supersedes.startswith("decisions/semantic-exhaustiveness/"):
            failures.append("supersedes precisa referenciar decisão de exaustividade semântica")
        if supersedes == relative_path:
            failures.append("decisão não pode superseder a si mesma")

    return failures


def _superseded_paths(records: dict[str, dict]) -> set[str]:
    return {
        record["supersedes"]
        for record in records.values()
        if record.get("supersedes") is not None and record["supersedes"] in records
    }


def _validate_supersedes_graph(records: dict[str, dict]) -> list[str]:
    failures: list[str] = []
    successors: dict[str, list[str]] = {}
    for relative, record in records.items():
        supersedes = record.get("supersedes")
        if supersedes is None:
            continue
        target = records.get(supersedes)
        if target is None:
            failures.append(f"{relative}: supersedes inexistente: {supersedes}")
            continue
        successors.setdefault(supersedes, []).append(relative)
        if (
            target["subject"]["kind"] != record["subject"]["kind"]
            or target["subject"]["id"] != record["subject"]["id"]
        ):
            failures.append(f"{relative}: supersedes precisa manter o mesmo subject")

    for target, children in successors.items():
        if len(children) > 1:
            failures.append(
                f"{target}: cadeia supersedes não pode bifurcar: "
                + ", ".join(sorted(children))
            )

    for start in records:
        seen: set[str] = set()
        current: str | None = start
        while current is not None:
            if current in seen:
                failures.append(f"{start}: ciclo detectado na cadeia supersedes")
                break
            seen.add(current)
            record = records.get(current)
            if record is None:
                break
            current = record.get("supersedes")
    return failures


def load_decisions() -> tuple[dict[str, dict], list[str]]:
    records: dict[str, dict] = {}
    failures: list[str] = []
    if not DECISIONS_ROOT.exists():
        return records, failures

    for path in sorted(DECISIONS_ROOT.rglob("*.yaml")):
        relative = path.relative_to(ROOT).as_posix()
        try:
            record = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            failures.append(f"decisão inválida {relative}: {exc}")
            continue
        record_failures = validate_decision_record(record, relative)
        failures.extend(f"{relative}: {item}" for item in record_failures)
        records[relative] = record

    failures.extend(_validate_supersedes_graph(records))
    return records, failures


def _approved_matches(
    record: dict,
    *,
    kind: str,
    subject_id: str,
    digest: str,
    snapshot: dict,
) -> bool:
    return (
        record["decision"]["outcome"] == "approved"
        and record["subject"]["kind"] == kind
        and record["subject"]["id"] == subject_id
        and record["subject"]["semantic_content_sha256"] == digest
        and record["snapshot"] == snapshot
    )


def validate_governance() -> list[str]:
    failures: list[str] = []
    for schema_path in (DECISION_SCHEMA, TAXONOMY_SCHEMA, PROFILE_SCHEMA):
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except (OSError, ValueError) as exc:
            failures.append(f"schema inválido {schema_path.relative_to(ROOT).as_posix()}: {exc}")
    if failures:
        return failures

    try:
        taxonomy = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
        profiles = yaml.safe_load(PROFILES_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [str(exc)]

    failures.extend(schema_failures(TAXONOMY_SCHEMA, taxonomy))
    failures.extend(schema_failures(PROFILE_SCHEMA, profiles))
    if failures:
        return failures

    records, decision_failures = load_decisions()
    failures.extend(decision_failures)
    superseded = _superseded_paths(records)

    taxonomy_semantic = taxonomy_snapshot(taxonomy)
    taxonomy_digest = canonical_sha256(taxonomy_semantic)
    taxonomy_state = taxonomy["exhaustiveness"]
    taxonomy_ref = taxonomy_state["decision_reference"]
    if taxonomy_state["status"] == "established":
        record = records.get(taxonomy_ref)
        if (
            record is None
            or taxonomy_ref in superseded
            or not _approved_matches(
                record,
                kind="taxonomy",
                subject_id=TAXONOMY_ID,
                digest=taxonomy_digest,
                snapshot=taxonomy_semantic,
            )
        ):
            failures.append("taxonomy established exige decisão approved efetiva vinculada ao snapshot semântico atual")
    elif taxonomy_ref is not None:
        failures.append("taxonomy not_established precisa manter decision_reference null")

    profiles_by_id = {item["rule_id"]: item for item in profiles["rules"]}
    for rule_id, profile in profiles_by_id.items():
        semantic = profile_snapshot(profiles, profile)
        digest = canonical_sha256(semantic)
        state = profile["profile_exhaustiveness"]
        reference = state["decision_reference"]
        if state["status"] == "established":
            record = records.get(reference)
            if (
                record is None
                or reference in superseded
                or not _approved_matches(
                    record,
                    kind="rule_profile",
                    subject_id=rule_id,
                    digest=digest,
                    snapshot=semantic,
                )
            ):
                failures.append(
                    f"profile {rule_id} established exige decisão approved efetiva vinculada ao snapshot semântico atual"
                )
        elif reference is not None:
            failures.append(f"profile {rule_id} not_established precisa manter decision_reference null")

    current_subjects = {
        ("taxonomy", TAXONOMY_ID, taxonomy_digest): taxonomy_state["status"],
        **{
            ("rule_profile", rule_id, canonical_sha256(profile_snapshot(profiles, profile))):
            profile["profile_exhaustiveness"]["status"]
            for rule_id, profile in profiles_by_id.items()
        },
    }
    for relative, record in records.items():
        if relative in superseded or record["decision"]["outcome"] != "approved":
            continue
        key = (
            record["subject"]["kind"],
            record["subject"]["id"],
            record["subject"]["semantic_content_sha256"],
        )
        if key in current_subjects and current_subjects[key] != "established":
            failures.append(
                f"{relative}: decisão approved efetiva para snapshot atual não pode ficar dormente enquanto status é not_established"
            )

    return failures


def main() -> int:
    failures = validate_governance()
    if failures:
        for failure in failures:
            print(f"ERRO: {failure}", file=sys.stderr)
        return 1
    print("OK: governança de exaustividade semântica válida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
