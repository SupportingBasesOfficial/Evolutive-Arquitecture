from __future__ import annotations

import hashlib
import json
import unittest

from evolutive.provenance.observed_manifest_reader import observe
from scripts.provenance_producer_trust import OBSERVED_MANIFEST_SCHEMA


class ObservedProvenanceReaderTests(unittest.TestCase):
    def _schema(self) -> dict:
        return json.loads(OBSERVED_MANIFEST_SCHEMA.read_text(encoding="utf-8"))

    def test_duplicate_json_members_are_rejected(self) -> None:
        content = (
            '{"manifest_version":1,"constitution_version":"0.2.0",'
            '"constitution_version":"0.2.0","transformations":[]}'
        )
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        brokered = {
            "identity": "build/provenance.json",
            "kind": "build_manifest",
            "sha256": digest,
            "content": content,
        }
        artifacts = [
            {"identity": "build/provenance.json", "kind": "build_manifest", "sha256": digest}
        ]
        with self.assertRaisesRegex(ValueError, "membro duplicado"):
            observe(brokered, artifacts, self._schema())

    def test_duplicate_authorized_identity_is_rejected_even_when_binding_matches(self) -> None:
        payload = {
            "manifest_version": 1,
            "constitution_version": "0.2.0",
            "transformations": [
                {
                    "id": "gen",
                    "provenance_class": "generated_source",
                    "inputs": [{"identity": "in.meta", "kind": "metadata", "sha256": "a" * 64}],
                    "outputs": [{"identity": "out.py", "kind": "generated_source", "sha256": "b" * 64}],
                    "candidate_relations": ["data_contract_dependency"],
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
        duplicate = {"identity": "in.meta", "kind": "metadata", "sha256": "a" * 64}
        artifacts = [
            {"identity": "build/provenance.json", "kind": "build_manifest", "sha256": digest},
            duplicate,
            dict(duplicate),
            {"identity": "out.py", "kind": "generated_source", "sha256": "b" * 64},
        ]
        with self.assertRaisesRegex(ValueError, "identity duplicada"):
            observe(brokered, artifacts, self._schema())


if __name__ == "__main__":
    unittest.main()
