from __future__ import annotations

import copy
import hashlib
import json
import unittest

from evolutive.provenance.observed_manifest_reader import observe
from scripts.provenance_producer_trust import (
    OBSERVED_MANIFEST_SCHEMA,
    attest_observed_producer_trust,
)
from scripts.provenance_semantic_interpretation import interpret_observed_provenance
from scripts.semantic_relation_evidence_aggregation import aggregate_semantic_relation_evidence


class SemanticRelationEvidenceAggregationTests(unittest.TestCase):
    def _bundle(self, suffix: str = "a") -> dict:
        payload = {
            "manifest_version": 1,
            "constitution_version": "0.2.0",
            "transformations": [
                {
                    "id": f"native-link-{suffix}",
                    "provenance_class": "linker_binding",
                    "inputs": [
                        {"identity": f"build/{suffix}.o", "kind": "object", "sha256": "a" * 64},
                        {"identity": f"vendor/{suffix}.a", "kind": "library", "sha256": "b" * 64},
                    ],
                    "outputs": [
                        {"identity": f"dist/{suffix}.bin", "kind": "binary", "sha256": "c" * 64}
                    ],
                    "candidate_relations": ["ffi_native_linkage"],
                }
            ],
        }
        content = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        brokered = {
            "identity": f"build/provenance-{suffix}.json",
            "kind": "build_manifest",
            "sha256": digest,
            "content": content,
        }
        artifacts = [
            {"identity": brokered["identity"], "kind": "build_manifest", "sha256": digest},
            {"identity": f"build/{suffix}.o", "kind": "object", "sha256": "a" * 64},
            {"identity": f"vendor/{suffix}.a", "kind": "library", "sha256": "b" * 64},
            {"identity": f"dist/{suffix}.bin", "kind": "binary", "sha256": "c" * 64},
        ]
        schema = json.loads(OBSERVED_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
        evidence = observe(brokered, artifacts, schema)
        attestation = attest_observed_producer_trust(brokered, artifacts, evidence)
        interpretation = interpret_observed_provenance(brokered, artifacts, evidence, attestation)
        return {
            "brokered_manifest": brokered,
            "authorized_artifacts": artifacts,
            "provenance_evidence": evidence,
            "trust_attestation": attestation,
            "semantic_interpretation": interpretation,
        }

    def test_aggregates_local_ffi_evidence_without_coverage_claim(self) -> None:
        result = aggregate_semantic_relation_evidence([self._bundle("a"), self._bundle("b")])
        self.assertEqual(len(result["relations"]), 1)
        relation = result["relations"][0]
        self.assertEqual(relation["relation_id"], "ffi_native_linkage")
        self.assertTrue(relation["has_proven_local_evidence"])
        self.assertEqual(relation["coverage_claim"], "none")
        self.assertEqual(len(relation["occurrences"]), 2)
        self.assertFalse(result["authority"]["may_assert_relation_coverage"])
        self.assertFalse(result["authority"]["may_assert_complete_rule_semantics"])
        self.assertFalse(result["authority"]["may_assert_rule_outcome"])

    def test_duplicate_interpretation_is_rejected(self) -> None:
        bundle = self._bundle()
        with self.assertRaises(ValueError):
            aggregate_semantic_relation_evidence([bundle, copy.deepcopy(bundle)])

    def test_forged_interpretation_is_rejected_by_fresh_recomputation(self) -> None:
        bundle = self._bundle()
        bundle["semantic_interpretation"] = copy.deepcopy(bundle["semantic_interpretation"])
        bundle["semantic_interpretation"]["results"][0]["outputs"][0]["sha256"] = "d" * 64
        with self.assertRaises(ValueError):
            aggregate_semantic_relation_evidence([bundle])

    def test_empty_bundle_list_produces_no_positive_relation_claim(self) -> None:
        result = aggregate_semantic_relation_evidence([])
        self.assertEqual(result["relations"], [])
        self.assertEqual(result["subject"]["interpretation_sha256s"], [])


if __name__ == "__main__":
    unittest.main()
