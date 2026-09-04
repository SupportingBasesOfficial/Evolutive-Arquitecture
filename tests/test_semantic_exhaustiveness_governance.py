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
    _effective_paths,
    _validate_decision_chains,
    expected_decision_path,
    taxonomy_snapshot,
    validate_decision_record,
    validate_governance,
)


class SemanticExhaustivenessGovernanceTests(unittest.TestCase):
    def taxonomy_record(self, sequence: int = 1) -> dict:
        taxonomy = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
        snapshot = taxonomy_snapshot(taxonomy)
        digest = canonical_sha256(snapshot)
        return {
            "decision_version": 1,
            "sequence": sequence,
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
        self.assertEqual(validate_decision_record(record, expected_decision_path(record)), [])

    def test_historical_decision_keeps_its_original_constitution_version(self) -> None:
        record = self.taxonomy_record()
        record["constitution_version"] = "0.1.0"
        record["snapshot"]["constitution_version"] = "0.1.0"
        record["subject"]["semantic_content_sha256"] = canonical_sha256(record["snapshot"])
        self.assertEqual(validate_decision_record(record, expected_decision_path(record)), [])

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

    def test_sequence_one_requires_null_supersedes(self) -> None:
        first = self.taxonomy_record(1)
        first["supersedes"] = "decisions/semantic-exhaustiveness/taxonomy/0-old-rejected.yaml"
        path = expected_decision_path(first)
        failures = _validate_decision_chains({path: first})
        self.assertTrue(any("sequence 1" in item for item in failures))

    def test_sequences_are_contiguous(self) -> None:
        first = self.taxonomy_record(1)
        first_path = expected_decision_path(first)
        third = self.taxonomy_record(3)
        third["supersedes"] = first_path
        third_path = expected_decision_path(third)
        failures = _validate_decision_chains({first_path: first, third_path: third})
        self.assertTrue(any("contígua" in item for item in failures))

    def test_next_sequence_must_supersede_exact_predecessor(self) -> None:
        first = self.taxonomy_record(1)
        first_path = expected_decision_path(first)
        second = self.taxonomy_record(2)
        second["supersedes"] = None
        second_path = expected_decision_path(second)
        failures = _validate_decision_chains({first_path: first, second_path: second})
        self.assertTrue(any("superseder exatamente" in item for item in failures))

    def test_approved_rejected_approved_chain_is_linear_and_reversible(self) -> None:
        first = self.taxonomy_record(1)
        first_path = expected_decision_path(first)

        second = self.taxonomy_record(2)
        second["decision"]["outcome"] = "rejected"
        second["decision"]["rationale"] = (
            "A later adversarial review found a blocker and revokes the previous exhaustiveness conclusion."
        )
        second["supersedes"] = first_path
        second_path = expected_decision_path(second)

        third = self.taxonomy_record(3)
        third["decision"]["rationale"] = (
            "A subsequent full review resolved the blocker and supports a new exhaustiveness conclusion without rewriting history."
        )
        third["supersedes"] = second_path
        third_path = expected_decision_path(third)

        records = {first_path: first, second_path: second, third_path: third}
        self.assertEqual(_validate_decision_chains(records), [])
        effective = _effective_paths(records)
        self.assertEqual(effective, {third_path})

    def test_duplicate_sequence_for_same_subject_is_rejected(self) -> None:
        first = self.taxonomy_record(1)
        second = copy.deepcopy(first)
        second["decision"]["outcome"] = "rejected"
        first_path = expected_decision_path(first)
        second_path = expected_decision_path(second)
        # Force a distinct dictionary key while preserving the invalid duplicate sequence.
        records = {first_path: first, second_path + ".duplicate": second}
        failures = _validate_decision_chains(records)
        self.assertTrue(any("sequence duplicada" in item for item in failures))

    def test_taxonomy_schema_requires_null_reference_while_not_established(self) -> None:
        taxonomy = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
        forged = copy.deepcopy(taxonomy)
        forged["exhaustiveness"]["decision_reference"] = (
            "decisions/semantic-exhaustiveness/taxonomy/1-"
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
