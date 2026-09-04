from __future__ import annotations

import copy
import hashlib
import json
import unittest

import yaml

from evolutive.provenance.observed_manifest_reader import observe
from scripts.provenance_producer_trust import (
    OBSERVED_MANIFEST_SCHEMA,
    attest_observed_producer_trust,
)
from scripts.provenance_semantic_interpretation import (
    POLICY,
    _validate_policy,
    interpret_observed_provenance,
)


class ProvenanceSemanticInterpretationTests(unittest.TestCase):
    def _fixture(self, provenance_class: str = "linker_binding", relation: str = "ffi_native_linkage") -> tuple[dict, list[dict], dict, dict]:
        payload = {
            "manifest_version": 1,
            "constitution_version": "0.2.0",
            "transformations": [
                {
                    "id": "native-link",
                    "provenance_class": provenance_class,
                    "inputs": [
                        {"identity": "build/native.o", "kind": "object", "sha256": "a" * 64},
                        {"identity": "vendor/libnative.a", "kind": "library", "sha256": "b" * 64},
                    ],
                    "outputs": [
                        {"identity": "dist/app.bin", "kind": "binary", "sha256": "c" * 64}
                    ],
                    "candidate_relations": [relation],
                }
            ],
        }
        content = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        brokered = {
            "identity": "build/provenance.json",
            "kind": "build_manifest",
            "sha256": digest,
            "content": content,
        }
        artifacts = [
            {"identity": "build/provenance.json", "kind": "build_manifest", "sha256": digest},
            {"identity": "build/native.o", "kind": "object", "sha256": "a" * 64},
            {"identity": "vendor/libnative.a", "kind": "library", "sha256": "b" * 64},
            {"identity": "dist/app.bin", "kind": "binary", "sha256": "c" * 64},
        ]
        schema = json.loads(OBSERVED_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
        evidence = observe(brokered, artifacts, schema)
        attestation = attest_observed_producer_trust(brokered, artifacts, evidence)
        return brokered, artifacts, evidence, attestation

    def test_verified_observed_linker_binding_proves_only_local_ffi_relation(self) -> None:
        brokered, artifacts, evidence, attestation = self._fixture()
        result = interpret_observed_provenance(brokered, artifacts, evidence, attestation)
        self.assertEqual(len(result["results"]), 1)
        semantic = result["results"][0]
        self.assertEqual(semantic["semantic_relation"], "ffi_native_linkage")
        self.assertEqual(semantic["verdict"], "proven")
        self.assertEqual(semantic["scope"], "transformation_local")
        self.assertEqual(semantic["inputs"], evidence["transformations"][0]["inputs"])
        self.assertEqual(semantic["outputs"], evidence["transformations"][0]["outputs"])
        self.assertTrue(result["authority"]["semantic_evidence_only"])
        self.assertFalse(result["authority"]["may_assert_rule_outcome"])
        self.assertFalse(result["authority"]["may_assert_complete_rule_semantics"])

    def test_non_authorized_candidate_relation_produces_no_positive_semantic_result(self) -> None:
        brokered, artifacts, evidence, attestation = self._fixture("build_graph_binding", "configuration_binding")
        result = interpret_observed_provenance(brokered, artifacts, evidence, attestation)
        self.assertEqual(result["results"], [])

    def test_v010_rejects_second_policy_profile(self) -> None:
        policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
        forged = copy.deepcopy(policy)
        second = copy.deepcopy(forged["profiles"][0])
        second["id"] = "build-graph-to-configuration-binding"
        second["provenance_class"] = "build_graph_binding"
        second["semantic_relation"] = "configuration_binding"
        forged["profiles"].append(second)
        with self.assertRaisesRegex(ValueError, "exatamente um profile"):
            _validate_policy(forged, "0.2.0")

    def test_tampered_trust_attestation_is_rejected(self) -> None:
        brokered, artifacts, evidence, attestation = self._fixture()
        forged = copy.deepcopy(attestation)
        forged["subject"]["evidence_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            interpret_observed_provenance(brokered, artifacts, evidence, forged)

    def test_tampered_provenance_evidence_is_rejected_before_interpretation(self) -> None:
        brokered, artifacts, evidence, attestation = self._fixture()
        forged = copy.deepcopy(evidence)
        forged["transformations"][0]["outputs"][0]["sha256"] = "d" * 64
        with self.assertRaises(ValueError):
            interpret_observed_provenance(brokered, artifacts, forged, attestation)


if __name__ == "__main__":
    unittest.main()
