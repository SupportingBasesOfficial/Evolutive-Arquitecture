from __future__ import annotations

import copy
import json
import unittest

import yaml
from jsonschema import Draft202012Validator

from scripts.validate_build_time_provenance_governance import (
    EVIDENCE_SCHEMA,
    EVIDENCE_TEMPLATE,
    MAPPING_SCHEMA,
    PROVENANCE_TAXONOMY,
    SEMANTIC_MAPPING,
    TAXONOMY_SCHEMA,
    validate_contracts,
    validate_evidence,
)


class BuildTimeProvenanceGovernanceTests(unittest.TestCase):
    def test_current_contracts_are_valid(self) -> None:
        self.assertEqual(validate_contracts(), [])

    def test_taxonomy_authority_cannot_assert_semantic_exhaustiveness(self) -> None:
        value = yaml.safe_load(PROVENANCE_TAXONOMY.read_text(encoding="utf-8"))
        schema = json.loads(TAXONOMY_SCHEMA.read_text(encoding="utf-8"))
        forged = copy.deepcopy(value)
        forged["authority"]["may_assert_semantic_exhaustiveness"] = True
        failures = list(Draft202012Validator(schema).iter_errors(forged))
        self.assertTrue(failures)

    def test_mapping_authority_cannot_create_semantic_relations(self) -> None:
        value = yaml.safe_load(SEMANTIC_MAPPING.read_text(encoding="utf-8"))
        schema = json.loads(MAPPING_SCHEMA.read_text(encoding="utf-8"))
        forged = copy.deepcopy(value)
        forged["authority"]["may_create_semantic_relation"] = True
        failures = list(Draft202012Validator(schema).iter_errors(forged))
        self.assertTrue(failures)

    def test_mapping_completeness_is_structurally_partial(self) -> None:
        value = yaml.safe_load(SEMANTIC_MAPPING.read_text(encoding="utf-8"))
        schema = json.loads(MAPPING_SCHEMA.read_text(encoding="utf-8"))
        forged = copy.deepcopy(value)
        forged["mappings"][0]["completeness"] = "complete"
        failures = list(Draft202012Validator(schema).iter_errors(forged))
        self.assertTrue(failures)

    def test_every_provenance_class_has_exactly_one_mapping(self) -> None:
        provenance = yaml.safe_load(PROVENANCE_TAXONOMY.read_text(encoding="utf-8"))
        mapping = yaml.safe_load(SEMANTIC_MAPPING.read_text(encoding="utf-8"))
        classes = [item["id"] for item in provenance["classes"]]
        mapped = [item["provenance_class"] for item in mapping["mappings"]]
        self.assertEqual(sorted(classes), sorted(mapped))
        self.assertEqual(len(mapped), len(set(mapped)))
        self.assertNotIn("source_declared", classes)

    def test_evidence_schema_cannot_assert_semantic_outcome(self) -> None:
        schema = json.loads(EVIDENCE_SCHEMA.read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertNotIn("rule_outcome", properties)
        self.assertNotIn("pass", properties)
        transformation = properties["transformations"]["items"]["properties"]
        self.assertNotIn("semantic_relation_proven", transformation)
        authority = properties["authority"]["properties"]
        self.assertEqual(authority["producer_trust"]["const"], "unverified")
        self.assertFalse(authority["may_assert_semantic_relation"]["const"])
        self.assertFalse(authority["may_assert_rule_outcome"]["const"])

    def test_arbitrary_evidence_rejects_unknown_provenance_class(self) -> None:
        evidence = yaml.safe_load(EVIDENCE_TEMPLATE.read_text(encoding="utf-8"))
        forged = copy.deepcopy(evidence)
        forged["transformations"][0]["provenance_class"] = "invented_provenance"
        failures = validate_evidence(forged)
        self.assertTrue(any("provenance_class desconhecida" in item for item in failures))

    def test_arbitrary_evidence_rejects_candidate_outside_mapping(self) -> None:
        evidence = yaml.safe_load(EVIDENCE_TEMPLATE.read_text(encoding="utf-8"))
        forged = copy.deepcopy(evidence)
        forged["transformations"][0]["candidate_relations"] = ["interprocess_dependency"]
        failures = validate_evidence(forged)
        self.assertTrue(any("candidate_relations fora do mapping" in item for item in failures))

    def test_arbitrary_evidence_rejects_duplicate_transformation_ids(self) -> None:
        evidence = yaml.safe_load(EVIDENCE_TEMPLATE.read_text(encoding="utf-8"))
        forged = copy.deepcopy(evidence)
        forged["transformations"].append(copy.deepcopy(forged["transformations"][0]))
        failures = validate_evidence(forged)
        self.assertTrue(any("transformation ids precisam ser únicos" in item for item in failures))

    def test_artifact_identity_cannot_bind_to_conflicting_content(self) -> None:
        evidence = yaml.safe_load(EVIDENCE_TEMPLATE.read_text(encoding="utf-8"))
        forged = copy.deepcopy(evidence)
        second = copy.deepcopy(forged["transformations"][0])
        second["id"] = "generated-client-conflict"
        second["inputs"][0]["sha256"] = "c" * 64
        forged["transformations"].append(second)
        failures = validate_evidence(forged)
        self.assertTrue(any("binding conflitante" in item for item in failures))

    def test_verified_producer_trust_is_rejected_by_v1_schema(self) -> None:
        evidence = yaml.safe_load(EVIDENCE_TEMPLATE.read_text(encoding="utf-8"))
        forged = copy.deepcopy(evidence)
        forged["authority"]["producer_trust"] = "verified"
        failures = validate_evidence(forged)
        self.assertTrue(any("schema:" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
