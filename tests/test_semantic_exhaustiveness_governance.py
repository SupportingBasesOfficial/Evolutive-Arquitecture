from __future__ import annotations

import copy
import json
import unittest

import yaml
from jsonschema import Draft202012Validator

from scripts.coverage_attestation import canonical_sha256
from scripts.validate_semantic_exhaustiveness_governance import (
    DECISION_SCHEMA,
    PROFILE_SCHEMA,
    PROFILES_PATH,
    TAXONOMY_ID,
    TAXONOMY_PATH,
    TAXONOMY_SCHEMA,
    _superseded_paths,
    _validate_supersedes_graph,
    expected_decision_path,
    taxonomy_snapshot,
    validate_decision_record,
    validate_governance,
)


class SemanticExhaustivenessGovernanceTests(unittest.TestCase):
    def taxonomy_record(self) -> dict:
        taxonomy = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
        snapshot = taxonomy_snapshot(taxonomy)
        digest = canonical_sha256(snapshot)
        return {
            "decision_version": 1,
            "constitution_version": "0.2.0",
            "subject": {
                "kind": "taxonomy",
                "id": TAXONOMY_ID,
                "semantic_content_sha256": digest,
                "target_status": "established",
            },
            "snapshot": snapshot,
            "review": {
                "dimensions": {
                    "normative_text_coverage": True,
                    "indirect_dependency_forms": True,
                    "dynamic_resolution": True,
                    "configuration_and_wiring": True,
                    "data_and_contract_coupling": True,
                    "cross_runtime_and_ffi": True,
                    "interprocess_and_distributed": True,
                    "behavioral_conventions": True,
                    "language_and_tooling_independence": True,
                    "adversarial_counterexample_review": True,
                },
                "counterexample_search": {
                    "performed": True,
                    "methods": [
                        "red-team enumeration across dependency mechanisms",
                        "cross-ecosystem review against independent language models",
                    ],
                    "cases": [],
                },
                "evidence": [
                    {
                        "kind": "normative_analysis",
                        "reference": "docs/example-normative-analysis.md",
                        "summary": "Maps every normative clause to the proposed semantic relation space.",
                    },
                    {
                        "kind": "adversarial_review",
                        "reference": "docs/example-red-team-review.md",
                        "summary": "Challenges the taxonomy with alternative dependency mechanisms.",
                    },
                ],
                "unresolved_gaps": [],
            },
            "decision": {
                "outcome": "approved",
                "authority": "SupportingBasesOfficial",
                "decided_at": "2026-09-04",
                "rationale": "All mandatory review dimensions and adversarial evidence support the bounded exhaustiveness claim.",
            },
            "supersedes": None,
        }

    def test_current_repository_governance_is_valid(self) -> None:
        self.assertEqual(validate_governance(), [])

    def test_well_formed_approved_taxonomy_decision_is_self_verifying(self) -> None:
        record = self.taxonomy_record()
        path = expected_decision_path(record)
        self.assertEqual(validate_decision_record(record, path), [])

    def test_historical_decision_keeps_its_original_constitution_version(self) -> None:
        record = self.taxonomy_record()
        record["constitution_version"] = "0.1.0"
        record["snapshot"]["constitution_version"] = "0.1.0"
        record["subject"]["semantic_content_sha256"] = canonical_sha256(record["snapshot"])
        path = expected_decision_path(record)
        self.assertEqual(validate_decision_record(record, path), [])

    def test_approved_decision_rejects_unreviewed_dimension(self) -> None:
        record = self.taxonomy_record()
        record["review"]["dimensions"]["dynamic_resolution"] = False
        failures = validate_decision_record(record, expected_decision_path(record))
        self.assertTrue(any("dimensões revisadas" in item for item in failures))

    def test_approved_decision_rejects_unresolved_gap_and_counterexample(self) -> None:
        record = self.taxonomy_record()
        record["review"]["unresolved_gaps"] = ["Reflection-based dependency class is not yet resolved."]
        record["review"]["counterexample_search"]["cases"] = [
            {
                "description": "Runtime reflection creates a dependency outside the proposed relation mapping.",
                "disposition": "unresolved",
                "rationale": "No existing relation currently accounts for this counterexample with sufficient precision.",
            }
        ]
        failures = validate_decision_record(record, expected_decision_path(record))
        self.assertTrue(any("unresolved_gaps" in item for item in failures))
        self.assertTrue(any("contraexemplo unresolved" in item for item in failures))

    def test_approved_decision_requires_independent_evidence_classes(self) -> None:
        record = self.taxonomy_record()
        record["review"]["evidence"][1]["kind"] = "normative_analysis"
        failures = validate_decision_record(record, expected_decision_path(record))
        self.assertTrue(any("classes distintas de evidência" in item for item in failures))

    def test_snapshot_digest_mismatch_is_rejected(self) -> None:
        record = self.taxonomy_record()
        record["snapshot"]["relations"][0]["description"] += " changed"
        failures = validate_decision_record(record, expected_decision_path(record))
        self.assertTrue(any("semantic_content_sha256" in item for item in failures))

    def test_noncanonical_decision_path_is_rejected(self) -> None:
        record = self.taxonomy_record()
        failures = validate_decision_record(
            record,
            "decisions/semantic-exhaustiveness/taxonomy/manual-approved.yaml",
        )
        self.assertTrue(any("caminho canônico" in item for item in failures))

    def test_supersedes_must_keep_same_subject(self) -> None:
        first = self.taxonomy_record()
        first["decision"]["outcome"] = "rejected"
        first_path = expected_decision_path(first)
        second = self.taxonomy_record()
        second["supersedes"] = first_path
        second_path = expected_decision_path(second)
        other = copy.deepcopy(first)
        other["subject"]["kind"] = "rule_profile"
        other["subject"]["id"] = "ARCH-002"
        records = {first_path: other, second_path: second}
        failures = _validate_supersedes_graph(records)
        self.assertTrue(any("mesmo subject" in item for item in failures))

    def test_supersedes_cycle_is_rejected(self) -> None:
        first = self.taxonomy_record()
        first["decision"]["outcome"] = "rejected"
        first_path = expected_decision_path(first)
        second = self.taxonomy_record()
        second["subject"]["semantic_content_sha256"] = "b" * 64
        second["decision"]["outcome"] = "rejected"
        second_path = expected_decision_path(second)
        first["supersedes"] = second_path
        second["supersedes"] = first_path
        failures = _validate_supersedes_graph({first_path: first, second_path: second})
        self.assertTrue(any("ciclo" in item for item in failures))

    def test_supersedes_chain_cannot_fork(self) -> None:
        base = self.taxonomy_record()
        base["decision"]["outcome"] = "rejected"
        base_path = expected_decision_path(base)
        first = self.taxonomy_record()
        first["supersedes"] = base_path
        second = copy.deepcopy(first)
        second["subject"]["semantic_content_sha256"] = "c" * 64
        first_path = expected_decision_path(first)
        second_path = expected_decision_path(second)
        failures = _validate_supersedes_graph(
            {base_path: base, first_path: first, second_path: second}
        )
        self.assertTrue(any("não pode bifurcar" in item for item in failures))

    def test_superseded_approval_is_not_effective(self) -> None:
        approved = self.taxonomy_record()
        approved_path = expected_decision_path(approved)
        rejected = copy.deepcopy(approved)
        rejected["decision"]["outcome"] = "rejected"
        rejected["decision"]["rationale"] = (
            "A later adversarial review found a blocker and revokes the previous exhaustiveness conclusion."
        )
        rejected["supersedes"] = approved_path
        rejected_path = expected_decision_path(rejected)
        superseded = _superseded_paths(
            {approved_path: approved, rejected_path: rejected}
        )
        self.assertIn(approved_path, superseded)
        self.assertNotIn(rejected_path, superseded)

    def test_taxonomy_schema_requires_null_reference_while_not_established(self) -> None:
        taxonomy = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
        forged = copy.deepcopy(taxonomy)
        forged["exhaustiveness"]["decision_reference"] = (
            "decisions/semantic-exhaustiveness/taxonomy/"
            + "a" * 64
            + "-approved.yaml"
        )
        schema = json.loads(TAXONOMY_SCHEMA.read_text(encoding="utf-8"))
        failures = list(Draft202012Validator(schema).iter_errors(forged))
        self.assertTrue(failures)

    def test_profile_schema_requires_approved_reference_when_established(self) -> None:
        profiles = yaml.safe_load(PROFILES_PATH.read_text(encoding="utf-8"))
        forged = copy.deepcopy(profiles)
        forged["rules"][0]["profile_exhaustiveness"]["status"] = "established"
        forged["rules"][0]["profile_exhaustiveness"]["decision_reference"] = None
        schema = json.loads(PROFILE_SCHEMA.read_text(encoding="utf-8"))
        failures = list(Draft202012Validator(schema).iter_errors(forged))
        self.assertTrue(failures)

    def test_decision_schema_is_valid_draft_2020_12(self) -> None:
        schema = json.loads(DECISION_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)


if __name__ == "__main__":
    unittest.main()
