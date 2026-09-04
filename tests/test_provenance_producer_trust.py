from __future__ import annotations

import copy
import unittest

from evolutive.provenance.declared_manifest_verifier import verify
from scripts.provenance_producer_trust import attest_producer_trust, validate_attestation


class ProvenanceProducerTrustTests(unittest.TestCase):
    def _fixture(self) -> tuple[dict, list[dict], dict]:
        declaration = {
            "constitution_version": "0.2.0",
            "transformations": [
                {
                    "id": "generated-client",
                    "provenance_class": "generated_source",
                    "inputs": [
                        {
                            "identity": "schemas/service-api.yaml",
                            "kind": "metadata",
                            "sha256": "a" * 64,
                        }
                    ],
                    "outputs": [
                        {
                            "identity": "generated/service_client.py",
                            "kind": "generated_source",
                            "sha256": "b" * 64,
                        }
                    ],
                    "candidate_relations": [
                        "source_module_dependency",
                        "data_contract_dependency",
                    ],
                    "observation_basis": "declared",
                }
            ],
        }
        artifacts = [
            {"identity": "schemas/service-api.yaml", "kind": "metadata", "sha256": "a" * 64},
            {
                "identity": "generated/service_client.py",
                "kind": "generated_source",
                "sha256": "b" * 64,
            },
        ]
        return declaration, artifacts, verify(declaration, artifacts)

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

    def test_producer_rejects_invalid_unreferenced_authorized_artifact(self) -> None:
        declaration, artifacts, _ = self._fixture()
        forged = copy.deepcopy(artifacts)
        forged.append({"identity": "unused.bin", "kind": "binary", "sha256": "not-a-sha"})
        with self.assertRaisesRegex(ValueError, "sha256 inválido"):
            verify(declaration, forged)

    def test_trust_attestation_is_reproducible_and_trust_only(self) -> None:
        declaration, artifacts, evidence = self._fixture()
        attestation = attest_producer_trust(declaration, artifacts, evidence)
        self.assertEqual(attestation["evaluation"]["verdict"], "verified")
        self.assertEqual(attestation["producer"]["observation_basis"], "declared")
        self.assertEqual(attestation["evaluator"]["id"], "evolutive.provenance.producer_trust_attestor")
        self.assertTrue(attestation["authority"]["trust_only"])
        self.assertFalse(attestation["authority"]["may_assert_semantic_relation"])
        self.assertFalse(attestation["authority"]["may_assert_rule_outcome"])
        validate_attestation(attestation, declaration, artifacts, evidence)

    def test_attestation_refuses_tampered_evidence(self) -> None:
        declaration, artifacts, evidence = self._fixture()
        forged = copy.deepcopy(evidence)
        forged["transformations"][0]["notes"] = "tampered"
        with self.assertRaises(ValueError):
            attest_producer_trust(declaration, artifacts, forged)

    def test_existing_attestation_invalid_after_authorized_binding_changes(self) -> None:
        declaration, artifacts, evidence = self._fixture()
        attestation = attest_producer_trust(declaration, artifacts, evidence)
        changed = copy.deepcopy(artifacts)
        changed[1]["sha256"] = "d" * 64
        with self.assertRaises(ValueError):
            validate_attestation(attestation, declaration, changed, evidence)

    def test_existing_attestation_invalid_after_unreferenced_scope_change(self) -> None:
        declaration, artifacts, evidence = self._fixture()
        attestation = attest_producer_trust(declaration, artifacts, evidence)
        changed = copy.deepcopy(artifacts)
        changed.append({"identity": "unreferenced.bin", "kind": "binary", "sha256": "e" * 64})
        with self.assertRaisesRegex(ValueError, "attestation diverge"):
            validate_attestation(attestation, declaration, changed, evidence)


if __name__ == "__main__":
    unittest.main()
