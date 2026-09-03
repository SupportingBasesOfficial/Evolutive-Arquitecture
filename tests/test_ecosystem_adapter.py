from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import yaml

from evolutive.adapters.python_imports import adapt
from evolutive.checkers.architecture import evaluate_architecture
from scripts.adapter_broker import build_adapter_request
from scripts.architecture_evidence import validate_architecture_evidence
from scripts.architecture_policy import validate_architecture_policy
from scripts.assemble_architecture_evidence import assemble_evidence
from scripts.generate_architecture_evidence import generate_architecture_evidence
from scripts.run_adapter import canonical_bytes, execute_adapter
from scripts.validate_adapter_contract import MANIFEST_TEMPLATE
from scripts.validate_project_config import DEFAULT_CONFIG


class EcosystemAdapterTests(unittest.TestCase):
    def prepare(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory) / "consumer"
        (root / ".evolutive").mkdir(parents=True)
        (root / "src/core/contracts").mkdir(parents=True)
        (root / "src/core/internal").mkdir(parents=True)
        (root / "src/infrastructure").mkdir(parents=True)
        config = root / ".evolutive/config.yaml"
        config.write_text(DEFAULT_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
        policy = {
            "policy_version": 1,
            "constitution_version": "0.2.0",
            "components": [
                {
                    "id": "core",
                    "roots": ["src/core"],
                    "may_depend_on": [],
                    "public_surface": ["src/core/contracts/**"],
                },
                {
                    "id": "infrastructure",
                    "roots": ["src/infrastructure"],
                    "may_depend_on": ["core"],
                    "public_surface": [],
                },
            ],
        }
        (root / ".evolutive/architecture-policy.yaml").write_text(
            yaml.safe_dump(policy, sort_keys=False), encoding="utf-8"
        )
        (root / "src/core/contracts/repository.py").write_text("class Repository: pass\n", encoding="utf-8")
        (root / "src/core/internal/secret.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "src/core/use.py").write_text("import infrastructure.repo\n", encoding="utf-8")
        (root / "src/infrastructure/repo.py").write_text("from core.internal import secret\n", encoding="utf-8")
        return root, config

    def manifest_with_current_digest(self, directory: str) -> Path:
        manifest = yaml.safe_load(MANIFEST_TEMPLATE.read_text(encoding="utf-8"))
        implementation = Path(__file__).resolve().parents[1] / "evolutive/adapters/python_imports.py"
        manifest["runtime"]["implementation_sha256"] = hashlib.sha256(canonical_bytes(implementation)).hexdigest()
        path = Path(directory) / "adapter.yaml"
        path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        return path

    def test_python_adapter_builds_cross_component_edges_and_preserves_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            request, audit = build_adapter_request(config, root, MANIFEST_TEMPLATE)
            result = adapt(request)
            self.assertEqual(result["coverage"]["files_received"], 4)
            self.assertEqual(result["coverage"]["files_parsed"], 4)
            self.assertEqual(result["coverage"]["unresolved_references"], 0)
            self.assertEqual(len(result["dependencies"]), 2)
            self.assertFalse(audit["project_root_disclosed"])

            manifest = self.manifest_with_current_digest(directory)
            evidence = assemble_evidence(config, root, manifest, result, audit)
            self.assertEqual(evidence["producer"]["kind"], "adapter")
            self.assertEqual(evidence["observation"]["coverage"], result["coverage"])
            self.assertEqual(evidence["observation"]["broker_audit"], audit)

            (root / ".evolutive/architecture-evidence.yaml").write_text(
                yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8"
            )
            _, failures = validate_architecture_evidence(config, root)
            self.assertEqual(failures, [])

            findings = evaluate_architecture(evidence["graph"])
            self.assertEqual(len(findings["ARCH-002"]), 1)
            self.assertEqual(len(findings["MOD-001"]), 2)

    def test_safe_pipeline_preserves_broker_and_adapter_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            evidence = generate_architecture_evidence(config, root, MANIFEST_TEMPLATE)
            self.assertEqual(evidence["producer"]["id"], "evolutive.python.imports")
            self.assertEqual(evidence["observation"]["coverage"]["files_received"], 4)
            self.assertEqual(evidence["observation"]["broker_audit"]["files_delivered"], 4)
            self.assertFalse(evidence["observation"]["broker_audit"]["project_root_disclosed"])

    def test_broker_skip_is_preserved_in_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/non_utf8.py").write_bytes(b"\xff")
            request, audit = build_adapter_request(config, root, MANIFEST_TEMPLATE)
            result = adapt(request)
            manifest = self.manifest_with_current_digest(directory)
            evidence = assemble_evidence(config, root, manifest, result, audit)

            self.assertEqual(result["coverage"]["files_received"], 4)
            self.assertEqual(audit["files_delivered"], 4)
            self.assertTrue(any(item["path"] == "src/core/non_utf8.py" for item in audit["skipped"]))
            self.assertEqual(evidence["observation"]["broker_audit"]["skipped"], audit["skipped"])

    def test_assembler_rejects_broker_coverage_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            request, audit = build_adapter_request(config, root, MANIFEST_TEMPLATE)
            result = adapt(request)
            manifest = self.manifest_with_current_digest(directory)
            audit["files_delivered"] += 1
            with self.assertRaisesRegex(ValueError, "files_delivered"):
                assemble_evidence(config, root, manifest, result, audit)

    def test_runner_accepts_only_digest_pinned_registered_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            request, _ = build_adapter_request(config, root, MANIFEST_TEMPLATE)
            manifest = self.manifest_with_current_digest(directory)
            result = execute_adapter(manifest, request)
            self.assertEqual(result["adapter_id"], "evolutive.python.imports")

            data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            data["runtime"]["implementation_sha256"] = "0" * 64
            manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "implementation_sha256 diverge"):
                execute_adapter(manifest, request)

    def test_parse_failure_is_audited_instead_of_inventing_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            (root / "src/core/broken.py").write_text("def broken(:\n", encoding="utf-8")
            request, _ = build_adapter_request(config, root, MANIFEST_TEMPLATE)
            result = adapt(request)
            self.assertEqual(result["coverage"]["files_received"], 5)
            self.assertEqual(result["coverage"]["files_parsed"], 4)
            self.assertEqual(result["errors"][0]["code"], "PARSE_ERROR")

    def test_policy_rejects_overlapping_component_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            policy_path = root / ".evolutive/architecture-policy.yaml"
            policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
            policy["components"][1]["roots"] = ["src/core/internal"]
            policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
            _, failures = validate_architecture_policy(config, root)
            self.assertTrue(any("se sobrepõem" in item for item in failures))

    def test_policy_rejects_invalid_consumer_config_before_reading_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            data = yaml.safe_load(config.read_text(encoding="utf-8"))
            data["scope"]["roots"] = ["."]
            config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            _, failures = validate_architecture_policy(config, root)
            self.assertTrue(any("configuração inválida" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
