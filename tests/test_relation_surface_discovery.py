from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.relation_surface_discovery import discover_relation_surfaces


class RelationSurfaceDiscoveryTests(unittest.TestCase):
    def _project(self) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "build").mkdir(parents=True)
        config = {
            "config_version": 1,
            "constitution": {
                "version": "0.2.0",
                "artifact_url": "https://github.com/SupportingBasesOfficial/Evolutive-Arquitecture/releases/download/v0.2.0/evolutive-architecture-0.2.0.zip",
                "sha256": "a" * 64,
            },
            "profiles": ["universal"],
            "scope": {"roots": ["build"], "exclude": []},
            "mode": "report",
        }
        config_path = root / "project-config.yaml"
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        return temporary, root, config_path

    def _descriptor(self, identity: str, sha256: str) -> dict:
        return {
            "descriptor_version": 1,
            "constitution_version": "0.2.0",
            "relation_id": "ffi_native_linkage",
            "surface_kind": "linker_manifest",
            "kind_basis": "declared",
            "target": {
                "identity": identity,
                "kind": "build_manifest",
                "sha256": sha256,
            },
        }

    def _write_surface(self, root: Path, stem: str = "native") -> tuple[str, str]:
        target_identity = f"build/{stem}-manifest.json"
        target_content = b'{"transformations":[]}'
        (root / target_identity).write_bytes(target_content)
        target_sha = hashlib.sha256(target_content).hexdigest()
        descriptor_identity = f"build/{stem}.evolutive-linker-surface.json"
        (root / descriptor_identity).write_text(
            json.dumps(self._descriptor(target_identity, target_sha), sort_keys=True),
            encoding="utf-8",
        )
        return target_identity, target_sha

    def _declaration(self, identity: str, sha256: str) -> dict:
        return {
            "declaration_version": 1,
            "constitution_version": "0.2.0",
            "relation_id": "ffi_native_linkage",
            "surfaces": [{
                "identity": identity,
                "surface_kind": "linker_manifest",
                "kind_basis": "declared",
                "sha256": sha256,
            }],
        }

    def test_discovers_canonical_descriptor_and_reports_undeclared_target(self) -> None:
        temporary, root, config = self._project()
        self.addCleanup(temporary.cleanup)
        target_identity, _ = self._write_surface(root)
        result = discover_relation_surfaces(config, root)
        self.assertEqual(result["inventory"]["canonical_descriptor_discovery"], "complete")
        self.assertEqual(len(result["discovery"]["targets"]), 1)
        self.assertEqual(result["discovery"]["undeclared_targets"][0]["identity"], target_identity)
        self.assertEqual(result["discovery"]["project_relation_coverage_claim"], "none")
        self.assertFalse(result["authority"]["may_assert_surface_kind_authenticity"])
        self.assertFalse(result["authority"]["may_assert_project_relation_coverage"])

    def test_declared_target_is_not_reported_as_undeclared(self) -> None:
        temporary, root, config = self._project()
        self.addCleanup(temporary.cleanup)
        identity, sha256 = self._write_surface(root)
        result = discover_relation_surfaces(config, root, self._declaration(identity, sha256))
        self.assertEqual(result["discovery"]["undeclared_targets"], [])

    def test_noncanonical_file_is_not_discovered(self) -> None:
        temporary, root, config = self._project()
        self.addCleanup(temporary.cleanup)
        (root / "build" / "ordinary.json").write_text("{}", encoding="utf-8")
        result = discover_relation_surfaces(config, root)
        self.assertEqual(result["discovery"]["descriptors"], [])
        self.assertEqual(result["discovery"]["targets"], [])
        self.assertEqual(result["discovery"]["project_relation_coverage_claim"], "none")

    def test_invalid_canonical_descriptor_fails_closed(self) -> None:
        temporary, root, config = self._project()
        self.addCleanup(temporary.cleanup)
        (root / "build" / "bad.evolutive-linker-surface.json").write_text(
            '{"descriptor_version":1}', encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            discover_relation_surfaces(config, root)

    def test_target_hash_mismatch_fails_closed(self) -> None:
        temporary, root, config = self._project()
        self.addCleanup(temporary.cleanup)
        identity, _ = self._write_surface(root)
        (root / identity).write_bytes(b"changed")
        with self.assertRaises(ValueError):
            discover_relation_surfaces(config, root)

    def test_multiple_descriptors_for_same_target_fail_closed(self) -> None:
        temporary, root, config = self._project()
        self.addCleanup(temporary.cleanup)
        identity, sha256 = self._write_surface(root, "one")
        (root / "build" / "two.evolutive-linker-surface.json").write_text(
            json.dumps(self._descriptor(identity, sha256), sort_keys=True),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            discover_relation_surfaces(config, root)

    def test_canonical_descriptor_cannot_be_target(self) -> None:
        temporary, root, config = self._project()
        self.addCleanup(temporary.cleanup)
        target_identity = "build/target.evolutive-linker-surface.json"
        target_content = b"{}"
        (root / target_identity).write_bytes(target_content)
        descriptor = self._descriptor(target_identity, hashlib.sha256(target_content).hexdigest())
        (root / "build" / "source.evolutive-linker-surface.json").write_text(
            json.dumps(descriptor, sort_keys=True), encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            discover_relation_surfaces(config, root)

    def test_missing_authorized_root_makes_canonical_discovery_incomplete(self) -> None:
        temporary, root, config_path = self._project()
        self.addCleanup(temporary.cleanup)
        self._write_surface(root)
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["scope"]["roots"].append("missing-build")
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        result = discover_relation_surfaces(config_path, root)
        self.assertEqual(result["inventory"]["canonical_descriptor_discovery"], "incomplete")
        self.assertEqual(result["discovery"]["project_relation_coverage_claim"], "none")


if __name__ == "__main__":
    unittest.main()
