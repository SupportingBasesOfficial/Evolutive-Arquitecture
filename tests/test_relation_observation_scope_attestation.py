from __future__ import annotations

import copy
import hashlib
import json
import unittest

from evolutive.provenance.observed_manifest_reader import observe
from scripts.provenance_producer_trust import OBSERVED_MANIFEST_SCHEMA, attest_observed_producer_trust
from scripts.provenance_semantic_interpretation import interpret_observed_provenance
from scripts.relation_observation_scope_attestation import attest_relation_observation_scope
from scripts.semantic_relation_evidence_aggregation import aggregate_semantic_relation_evidence


class RelationObservationScopeAttestationTests(unittest.TestCase):
    def _bundle(self, suffix: str) -> dict:
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

    def _scope(self, *bundles: dict) -> dict:
        return {
            "scope_version": 1,
            "constitution_version": "0.2.0",
            "scope_type": "brokered_manifest_set",
            "relation_id": "ffi_native_linkage",
            "manifests": [
                {
                    "identity": bundle["brokered_manifest"]["identity"],
                    "sha256": bundle["brokered_manifest"]["sha256"],
                }
                for bundle in bundles
            ],
        }

    def test_complete_closed_scope_does_not_claim_project_coverage(self) -> None:
        bundles = [self._bundle("a"), self._bundle("b")]
        aggregation = aggregate_semantic_relation_evidence(bundles)
        result = attest_relation_observation_scope(self._scope(*bundles), bundles, aggregation)
        self.assertEqual(result["evaluation"]["scope_coverage"], "complete")
        self.assertEqual(result["evaluation"]["project_relation_coverage_claim"], "none")
        self.assertTrue(result["evaluation"]["criteria"]["declared_scope_matches_bundles"])
        self.assertEqual(result["evaluation"]["counts"]["positive_occurrences"], 2)
        self.assertFalse(result["authority"]["may_assert_project_relation_coverage"])
        self.assertFalse(result["authority"]["may_assert_complete_rule_semantics"])
        self.assertFalse(result["authority"]["may_assert_rule_outcome"])

    def test_scope_identity_is_order_invariant(self) -> None:
        first = self._bundle("a")
        second = self._bundle("b")
        bundles = [first, second]
        aggregation = aggregate_semantic_relation_evidence(bundles)
        forward = attest_relation_observation_scope(self._scope(first, second), bundles, aggregation)
        reverse = attest_relation_observation_scope(self._scope(second, first), bundles, aggregation)
        self.assertEqual(forward["subject"]["scope_sha256"], reverse["subject"]["scope_sha256"])
        self.assertEqual(forward["scope"], reverse["scope"])

    def test_missing_declared_manifest_yields_incomplete_scope(self) -> None:
        supplied = self._bundle("a")
        missing = self._bundle("b")
        aggregation = aggregate_semantic_relation_evidence([supplied])
        result = attest_relation_observation_scope(self._scope(supplied, missing), [supplied], aggregation)
        self.assertEqual(result["evaluation"]["scope_coverage"], "incomplete")
        self.assertFalse(result["evaluation"]["criteria"]["declared_scope_matches_bundles"])
        self.assertEqual(result["evaluation"]["project_relation_coverage_claim"], "none")

    def test_forged_interpretation_is_integrity_error_not_incomplete(self) -> None:
        bundle = self._bundle("a")
        aggregation = aggregate_semantic_relation_evidence([bundle])
        forged = copy.deepcopy(bundle)
        forged["semantic_interpretation"]["results"][0]["outputs"][0]["sha256"] = "d" * 64
        with self.assertRaises(ValueError):
            attest_relation_observation_scope(self._scope(bundle), [forged], aggregation)

    def test_duplicate_brokered_manifest_bundle_is_rejected(self) -> None:
        bundle = self._bundle("a")
        aggregation = aggregate_semantic_relation_evidence([bundle])
        with self.assertRaises(ValueError):
            attest_relation_observation_scope(self._scope(bundle), [bundle, copy.deepcopy(bundle)], aggregation)


if __name__ == "__main__":
    unittest.main()
