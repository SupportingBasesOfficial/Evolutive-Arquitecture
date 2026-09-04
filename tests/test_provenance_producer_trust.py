from __future__ import annotations

import copy
import hashlib
import json
import unittest

from evolutive.provenance.declared_manifest_verifier import verify
from evolutive.provenance.observed_manifest_reader import observe
from scripts.provenance_producer_trust import (
    OBSERVED_MANIFEST_SCHEMA,
    attest_observed_producer_trust,
    attest_producer_trust,
    validate_attestation,
    validate_observed_attestation,
)


class ProvenanceProducerTrustTests(unittest.TestCase):
    def _fixture(self) -> tuple[dict, list[dict], dict]:
        declaration = {
            "constitution_version": "0.2.0",
            "transformations": [
                {
                    "id": "generated-client",
                    "provenance_class": "generated_source",
                    "inputs": [{"identity": "schemas/service-api.yaml", "kind": "metadata", "sha256": "a" * 64}],
                    "outputs": [{"identity": "generated/service_client.py", "kind": "generated_source", "sha256": "b" * 64}],
                    "candidate_relations": ["source_module_dependency", "data_contract_dependency"],
                    "observation_basis": "declared",
                }
            ],
        }
        artifacts = [
            {"identity": "schemas/service-api.yaml", "kind": "metadata", "sha256": "a" * 64},
            {"identity": "generated/service_client.py", "kind": "generated_source", "sha256": "b" * 64},
        ]
        return declaration, artifacts, verify(declaration, artifacts)

    def _observed_fixture(self) -> tuple[dict, list[dict], dict]:
        payload = {
            "manifest_version": 1,
            "constitution_version": "0.2.0",
            "transformations": [
                {
                    "id": "generated-client",
                    "provenance_class": "generated_source",
                    "inputs": [{"identity": "schemas/service-api.yaml", "kind": "metadata", "sha256": "a" * 64}],
                    "outputs": [{"identity": "generated/service_client.py", "kind": "generated_source", "sha256": "b" * 64}],
                    "candidate_relations": ["source_module_dependency", "data_contract_dependency"],
                }
            ],
        }
        content = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        manifest_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        brokered_manifest = {
            "identity": "build/provenance.json",
            "kind": "build_manifest",
            "sha256": manifest_sha,
            "content": content,
        }
        artifacts = [
            {"identity": "build/provenance.json", "kind": "build_manifest", "sha256": manifest_sha},
            {"identity": "schemas/service-api.yaml", "kind": "metadata", "sha256": "a" * 64},
            {"identity": "generated/service_client.py", "kind": "generated_source", "sha256": "b" * 64},
        ]
        schema = json.loads(OBSERVED_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
        evidence = observe(brokered_manifest, artifacts, schema)
        return brokered_manifest, artifacts, evidence

    def test_declared_producer_reproduces_exact_evidence(self) -> None:
        declaration, artifacts, evidence = self._fixture()
        self.assertEqual(verify(declaration, artifacts), evidence)

    def test_producer_rejects_binding_drift(self) -> None:
        declaration, artifacts, _ = self._fixture()
        forged = copy.deepcopy(declaration)
        forged["transformations"][0]["outputs"][0]["sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "binding diverge"):
            verify(forged, artifacts)

    def test_producer_cannot_claim_observed_basis(self) -> None:
        declaration, artifacts, _ = self._fixture()
        forged = copy.deepcopy(declaration)
        forged["transformations"][0]["observation_basis"] = "observed"
        with self.assertRaisesRegex(ValueError, "observation_basis=declared"):
            verify(forged, artifacts)

    def test_producer_rejects_ignored_declaration_fields(self) -> None:
        declaration, artifacts, _ = self._fixture()
        forged = copy.deepcopy(declaration)
        forged["review_marker"] = "ignored-field"
        with self.assertRaisesRegex(ValueError, "declaration precisa conter somente"):
            verify(forged, artifacts)

    def test_trust_attestation_is_reproducible_and_trust_only(self) -> None:
        declaration, artifacts, evidence = self._fixture()
        attestation = attest_producer_trust(declaration, artifacts, evidence)
        self.assertEqual(attestation["evaluation"]["verdict"], "verified")
        self.assertEqual(attestation["producer"]["observation_basis"], "declared")
        self.assertEqual(attestation["evaluator"]["version"], "0.2.0")
        self.assertEqual(len(attestation["subject"]["producer_input_sha256"]), 64)
        self.assertEqual(len(attestation["subject"]["authorized_artifacts_sha256"]), 64)
        self.assertEqual(len(attestation["subject"]["evidence_sha256"]), 64)
        self.assertEqual(len(attestation["subject"]["governance_context_sha256"]), 64)
        self.assertTrue(attestation["authority"]["trust_only"])
        self.assertFalse(attestation["authority"]["may_assert_semantic_relation"])
        self.assertFalse(attestation["authority"]["may_assert_rule_outcome"])
        validate_attestation(attestation, declaration, artifacts, evidence)

    def test_authorized_artifact_order_does_not_change_attestation(self) -> None:
        declaration, artifacts, evidence = self._fixture()
        expected = attest_producer_trust(declaration, artifacts, evidence)
        reordered = attest_producer_trust(declaration, list(reversed(artifacts)), evidence)
        self.assertEqual(reordered, expected)

    def test_existing_attestation_invalid_after_unreferenced_scope_change(self) -> None:
        declaration, artifacts, evidence = self._fixture()
        attestation = attest_producer_trust(declaration, artifacts, evidence)
        changed = copy.deepcopy(artifacts)
        changed.append({"identity": "unreferenced.bin", "kind": "binary", "sha256": "e" * 64})
        with self.assertRaisesRegex(ValueError, "attestation diverge"):
            validate_attestation(attestation, declaration, changed, evidence)

    def test_observed_producer_reads_only_hash_bound_brokered_manifest(self) -> None:
        brokered_manifest, artifacts, evidence = self._observed_fixture()
        self.assertEqual(evidence["producer"]["id"], "evolutive.provenance.observed_manifest_reader")
        self.assertEqual(evidence["transformations"][0]["observation_basis"], "observed")
        self.assertEqual(evidence["authority"]["producer_trust"], "unverified")
        self.assertFalse(evidence["authority"]["may_assert_semantic_relation"])

    def test_observed_producer_rejects_manifest_content_hash_drift(self) -> None:
        brokered_manifest, artifacts, _ = self._observed_fixture()
        forged = copy.deepcopy(brokered_manifest)
        forged["content"] += " "
        schema = json.loads(OBSERVED_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "sha256.*diverge"):
            observe(forged, artifacts, schema)

    def test_observed_producer_rejects_unbrokered_transformation_artifact(self) -> None:
        brokered_manifest, artifacts, _ = self._observed_fixture()
        reduced = [artifact for artifact in artifacts if artifact["identity"] != "generated/service_client.py"]
        schema = json.loads(OBSERVED_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "artifact não autorizado"):
            observe(brokered_manifest, reduced, schema)

    def test_observed_trust_attestation_is_reproducible_and_trust_only(self) -> None:
        brokered_manifest, artifacts, evidence = self._observed_fixture()
        attestation = attest_observed_producer_trust(brokered_manifest, artifacts, evidence)
        self.assertEqual(attestation["producer"]["observation_basis"], "observed")
        self.assertEqual(attestation["evaluation"]["verdict"], "verified")
        self.assertTrue(attestation["authority"]["trust_only"])
        self.assertFalse(attestation["authority"]["may_assert_semantic_relation"])
        self.assertFalse(attestation["authority"]["may_assert_rule_outcome"])
        validate_observed_attestation(attestation, brokered_manifest, artifacts, evidence)

    def test_observed_attestation_invalid_after_brokered_content_change(self) -> None:
        brokered_manifest, artifacts, evidence = self._observed_fixture()
        attestation = attest_observed_producer_trust(brokered_manifest, artifacts, evidence)
        changed = copy.deepcopy(brokered_manifest)
        changed["content"] += " "
        with self.assertRaises(ValueError):
            validate_observed_attestation(attestation, changed, artifacts, evidence)

    def test_observed_evidence_does_not_prove_semantic_relation(self) -> None:
        _, _, evidence = self._observed_fixture()
        self.assertFalse(evidence["authority"]["may_assert_semantic_relation"])
        self.assertIn("data_contract_dependency", evidence["transformations"][0]["candidate_relations"])


if __name__ == "__main__":
    unittest.main()
