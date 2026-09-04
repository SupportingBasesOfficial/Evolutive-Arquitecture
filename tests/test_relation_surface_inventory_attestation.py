from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.relation_surface_inventory_attestation import attest_relation_surface_inventory


class RelationSurfaceInventoryAttestationTests(unittest.TestCase):
    def _project(self, files: dict[str, bytes]) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        config = {
            "config_version": 1,
            "constitution": {
                "version": "0.2.0",
                "artifact_url": "https://github.com/SupportingBasesOfficial/Evolutive-Arquitecture/releases/download/v0.2.0/evolutive-architecture-0.2.0.zip",
                "sha256": "a" * 64,
            },
            "profiles": ["universal"],
            "scope": {"roots": ["."], "exclude": [".evolutive/**"]},
            "mode": "report",
        }
        config_path = root / "project-config.yaml"
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        return temporary, root, config_path

    def _declaration(self, surfaces: list[tuple[str, bytes]]) -> dict:
        return {
            "declaration_version": 1,
            "constitution_version": "0.2.0",
            "relation_id": "ffi_native_linkage",
            "surfaces": [
                {
                    "identity": identity,
                    "surface_kind": "linker_manifest",
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
                for identity, content in surfaces
            ],
        }

    def test_aligned_declaration_does_not_claim_project_coverage(self) -> None:
        files = {"build/linker-a.json": b"a", "build/linker-b.json": b"b"}
        temporary, root, config = self._project(files)
        self.addCleanup(temporary.cleanup)
        declaration = self._declaration(list(files.items()))
        result = attest_relation_surface_inventory(declaration, config, root)
        self.assertEqual(result["evaluation"]["declared_surface_inventory"], "aligned")
        self.assertEqual(result["evaluation"]["project_relation_coverage_claim"], "none")
        self.assertEqual(result["evaluation"]["counts"]["hash_verified_surfaces"], 2)
        self.assertFalse(result["authority"]["may_assert_project_relation_coverage"])
        self.assertFalse(result["authority"]["may_assert_complete_rule_semantics"])
        self.assertFalse(result["authority"]["may_assert_rule_outcome"])

    def test_declaration_identity_is_order_invariant(self) -> None:
        files = {"build/a.json": b"a", "build/b.json": b"b"}
        temporary, root, config = self._project(files)
        self.addCleanup(temporary.cleanup)
        forward = self._declaration(list(files.items()))
        reverse = copy.deepcopy(forward)
        reverse["surfaces"].reverse()
        first = attest_relation_surface_inventory(forward, config, root)
        second = attest_relation_surface_inventory(reverse, config, root)
        self.assertEqual(first, second)

    def test_hash_mismatch_is_misaligned_not_coverage(self) -> None:
        files = {"build/linker.json": b"actual"}
        temporary, root, config = self._project(files)
        self.addCleanup(temporary.cleanup)
        declaration = self._declaration([("build/linker.json", b"different")])
        result = attest_relation_surface_inventory(declaration, config, root)
        self.assertEqual(result["evaluation"]["declared_surface_inventory"], "misaligned")
        self.assertIn("surface_hash_mismatch", result["evaluation"]["reasons"])
        self.assertEqual(result["evaluation"]["project_relation_coverage_claim"], "none")

    def test_excluded_surface_is_not_authorized(self) -> None:
        files = {".evolutive/linker.json": b"hidden"}
        temporary, root, config = self._project(files)
        self.addCleanup(temporary.cleanup)
        declaration = self._declaration(list(files.items()))
        result = attest_relation_surface_inventory(declaration, config, root)
        self.assertEqual(result["evaluation"]["declared_surface_inventory"], "misaligned")
        self.assertIn("surface_not_authorized", result["evaluation"]["reasons"])

    def test_path_escape_is_rejected(self) -> None:
        temporary, root, config = self._project({"build/linker.json": b"x"})
        self.addCleanup(temporary.cleanup)
        declaration = self._declaration([("../outside.json", b"x")])
        with self.assertRaises(ValueError):
            attest_relation_surface_inventory(declaration, config, root)


if __name__ == "__main__":
    unittest.main()
