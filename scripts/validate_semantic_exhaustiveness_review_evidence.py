#!/usr/bin/env python3
"""Valida pacotes auditáveis de evidência de revisão de exaustividade semântica."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

if __package__:
    from .coverage_attestation import canonical_sha256
    from .validate_semantic_exhaustiveness_governance import (
        PROFILES_PATH,
        TAXONOMY_ID,
        TAXONOMY_PATH,
        profile_snapshot,
        taxonomy_snapshot,
    )
else:
    from coverage_attestation import canonical_sha256
    from validate_semantic_exhaustiveness_governance import (
        PROFILES_PATH,
        TAXONOMY_ID,
        TAXONOMY_PATH,
        profile_snapshot,
        taxonomy_snapshot,
    )

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema" / "semantic-exhaustiveness-review-evidence.schema.json"
EVIDENCE_ROOT = ROOT / "evidence" / "semantic-exhaustiveness"


def schema_failures(value: object) -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(value))


def expected_path(package: dict) -> str:
    subject = package["subject"]
    digest = subject["semantic_content_sha256"]
    if subject["kind"] == "taxonomy":
        return f"evidence/semantic-exhaustiveness/taxonomy/{digest}-review.yaml"
    return f"evidence/semantic-exhaustiveness/rules/{subject['id']}/{digest}-review.yaml"


def _current_subjects() -> dict[tuple[str, str], dict]:
    taxonomy = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    profiles = yaml.safe_load(PROFILES_PATH.read_text(encoding="utf-8"))
    subjects: dict[tuple[str, str], dict] = {
        ("taxonomy", TAXONOMY_ID): taxonomy_snapshot(taxonomy)
    }
    for profile in profiles["rules"]:
        subjects[("rule_profile", profile["rule_id"])] = profile_snapshot(profiles, profile)
    return subjects


def validate_package(package: dict, relative_path: str, subjects: dict[tuple[str, str], dict]) -> list[str]:
    failures = schema_failures(package)
    if failures:
        return failures

    subject = package["subject"]
    key = (subject["kind"], subject["id"])
    snapshot = package["snapshot"]
    if package["constitution_version"] != snapshot["constitution_version"]:
        failures.append("constitution_version do pacote diverge do snapshot")

    digest = canonical_sha256(snapshot)
    if digest != subject["semantic_content_sha256"]:
        failures.append(f"semantic_content_sha256 diverge do snapshot: actual={digest}")

    expected = expected_path(package)
    if relative_path != expected:
        failures.append(f"caminho canônico inválido: esperado {expected}")

    current = subjects.get(key)
    if current is None:
        failures.append(f"subject desconhecido: {subject['kind']}:{subject['id']}")
    elif current != snapshot:
        failures.append("pacote de review precisa estar vinculado ao snapshot semântico atual")

    review = package["review"]
    dimensions = review["dimensions"]
    counterexamples = review["counterexamples"]
    residual = review["residual_gaps"]
    verdict = package["conclusion"]["verdict"]

    evidence_kinds = {item["kind"] for item in review["evidence"]}
    if len(evidence_kinds) < 2:
        failures.append("review evidence exige ao menos duas classes distintas de evidência")
    references = [item["reference"] for item in review["evidence"]]
    if len(references) != len(set(references)):
        failures.append("review evidence não pode duplicar referência")

    ids = [item["id"] for item in counterexamples]
    if len(ids) != len(set(ids)):
        failures.append("counterexample ids precisam ser únicos")

    relation_ids: set[str] = set()
    if subject["kind"] == "taxonomy":
        relation_ids = {item["id"] for item in snapshot["relations"]}
    else:
        relation_ids = {item["relation_id"] for item in snapshot["relations"]}
    for case in counterexamples:
        unknown = sorted(set(case.get("relation_ids", [])) - relation_ids)
        if unknown:
            failures.append(f"{case['id']}: relation_ids desconhecidos: {', '.join(unknown)}")

    statuses = {name: value["status"] for name, value in dimensions.items()}
    assessments = {item["assessment"] for item in counterexamples}

    if verdict == "supports_established":
        if any(value != "supported" for value in statuses.values()):
            failures.append("supports_established exige todas as dimensões supported")
        if residual:
            failures.append("supports_established não pode possuir residual_gaps")
        if assessments & {"potential_gap", "confirmed_gap"}:
            failures.append("supports_established não pode preservar counterexample gap")
    elif verdict == "supports_rejection":
        if "unsupported" not in statuses.values() and "confirmed_gap" not in assessments:
            failures.append("supports_rejection exige dimensão unsupported ou confirmed_gap")
    elif verdict == "inconclusive":
        if (
            "inconclusive" not in statuses.values()
            and "potential_gap" not in assessments
            and not residual
        ):
            failures.append("inconclusive exige incerteza ou gap residual explícito")

    return failures


def validate_repository_evidence() -> list[str]:
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        subjects = _current_subjects()
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [str(exc)]

    failures: list[str] = []
    if not EVIDENCE_ROOT.exists():
        return ["diretório de review evidence inexistente"]

    seen_subjects: set[tuple[str, str]] = set()
    for path in sorted(EVIDENCE_ROOT.rglob("*-review.yaml")):
        relative = path.relative_to(ROOT).as_posix()
        try:
            package = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            failures.append(f"{relative}: {exc}")
            continue
        package_failures = validate_package(package, relative, subjects)
        failures.extend(f"{relative}: {item}" for item in package_failures)
        if not package_failures:
            key = (package["subject"]["kind"], package["subject"]["id"])
            if key in seen_subjects:
                failures.append(f"{relative}: mais de um pacote current-review para o mesmo subject")
            seen_subjects.add(key)

    missing = sorted(set(subjects) - seen_subjects)
    if missing:
        failures.append(
            "faltam review packages para subjects atuais: "
            + ", ".join(f"{kind}:{subject_id}" for kind, subject_id in missing)
        )
    return failures


def main() -> int:
    failures = validate_repository_evidence()
    if failures:
        for failure in failures:
            print(f"ERRO: {failure}", file=sys.stderr)
        return 1
    print("OK: review evidence de exaustividade semântica válida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
