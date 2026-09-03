from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import yaml

from evolutive.adapters.ecmascript_imports import adapt, lex_module_tokens, module_specifiers
from evolutive.checkers.architecture import evaluate_architecture
from scripts.adapter_broker import build_adapter_request
from scripts.assemble_architecture_evidence import assemble_evidence
from scripts.run_adapter import canonical_bytes, execute_adapter
from scripts.validate_project_config import DEFAULT_CONFIG

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "adapters" / "ecmascript-imports.yaml"
IMPLEMENTATION = ROOT / "evolutive" / "adapters" / "ecmascript_imports.py"


class EcmaScriptAdapterTests(unittest.TestCase):
    def prepare(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory) / "consumer"
        (root / ".evolutive").mkdir(parents=True)
        (root / "src/core/contracts").mkdir(parents=True)
        (root / "src/core/internal").mkdir(parents=True)
        (root / "src/ui").mkdir(parents=True)
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
                    "id": "ui",
                    "roots": ["src/ui"],
                    "may_depend_on": ["core"],
                    "public_surface": [],
                },
            ],
        }
        (root / ".evolutive/architecture-policy.yaml").write_text(
            yaml.safe_dump(policy, sort_keys=False), encoding="utf-8"
        )
        (root / "src/core/contracts/public.ts").write_text(
            "export interface PublicContract {}\n", encoding="utf-8"
        )
        (root / "src/core/internal/secret.ts").write_text(
            "export const secret = 1;\n", encoding="utf-8"
        )
        (root / "src/core/use.ts").write_text(
            "import '../ui/view';\n", encoding="utf-8"
        )
        (root / "src/ui/view.tsx").write_text(
            "import React from 'react';\n"
            "import { secret } from '../core/internal/secret';\n"
            "export { PublicContract } from '../core/contracts/public';\n",
            encoding="utf-8",
        )
        return root, config

    def manifest_with_current_digest(self, directory: str) -> Path:
        manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        manifest["runtime"]["implementation_sha256"] = hashlib.sha256(
            canonical_bytes(IMPLEMENTATION)
        ).hexdigest()
        path = Path(directory) / "ecmascript-adapter.yaml"
        path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        return path

    def test_pipeline_produces_edges_and_preserves_bare_specifier_uncertainty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, config = self.prepare(directory)
            manifest = self.manifest_with_current_digest(directory)
            request, audit = build_adapter_request(config, root, manifest)
            result = execute_adapter(manifest, request)

            self.assertEqual(result["coverage"]["files_received"], 4)
            self.assertEqual(result["coverage"]["files_parsed"], 4)
            self.assertEqual(result["coverage"]["unresolved_references"], 1)
            self.assertEqual(len(result["dependencies"]), 3)
            self.assertFalse(audit["project_root_disclosed"])

            evidence = assemble_evidence(config, root, manifest, result, audit)
            findings = evaluate_architecture(evidence["graph"])
            self.assertEqual(len(findings["ARCH-002"]), 1)
            self.assertEqual(len(findings["MOD-001"]), 2)

    def test_scanner_ignores_comments_strings_regex_properties_and_require(self) -> None:
        tokens, error = lex_module_tokens(
            "// import './fake';\n"
            "const text = \"import('../string-fake')\";\n"
            "const pattern = /import\\('..\\/regex-fake'\\)/;\n"
            "client.import('../property-fake');\n"
            "require('../commonjs-uncertain');\n"
            "import './real';\n"
        )
        self.assertIsNone(error)
        self.assertEqual(module_specifiers(tokens), ["./real"])

    def test_interpolated_template_is_not_silently_counted_as_analyzed(self) -> None:
        result = adapt(
            {
                "request_version": 1,
                "adapter_id": "evolutive.ecmascript.imports",
                "constitution_version": "0.2.0",
                "components": [
                    {"id": "a", "roots": ["src/a"], "may_depend_on": [], "public_surface": []}
                ],
                "files": [
                    {
                        "path": "src/a/template.ts",
                        "size_bytes": 24,
                        "sha256": "0" * 64,
                        "text": "const x = `${import('./x')}`;",
                    }
                ],
            }
        )
        self.assertEqual(result["coverage"]["files_parsed"], 0)
        self.assertEqual(result["errors"][0]["code"], "LEX_ERROR")

    def test_ambiguous_extension_resolution_remains_unresolved(self) -> None:
        files = [
            {"path": "src/a/use.ts", "size_bytes": 20, "sha256": "0" * 64, "text": "import './target';\n"},
            {"path": "src/a/target.ts", "size_bytes": 0, "sha256": "0" * 64, "text": ""},
            {"path": "src/a/target.js", "size_bytes": 0, "sha256": "0" * 64, "text": ""},
        ]
        result = adapt(
            {
                "request_version": 1,
                "adapter_id": "evolutive.ecmascript.imports",
                "constitution_version": "0.2.0",
                "components": [
                    {"id": "a", "roots": ["src/a"], "may_depend_on": [], "public_surface": []}
                ],
                "files": files,
            }
        )
        self.assertEqual(result["dependencies"], [])
        self.assertEqual(result["coverage"]["unresolved_references"], 1)

    def test_unterminated_lexical_construct_reduces_coverage(self) -> None:
        result = adapt(
            {
                "request_version": 1,
                "adapter_id": "evolutive.ecmascript.imports",
                "constitution_version": "0.2.0",
                "components": [
                    {"id": "a", "roots": ["src/a"], "may_depend_on": [], "public_surface": []}
                ],
                "files": [
                    {
                        "path": "src/a/broken.ts",
                        "size_bytes": 14,
                        "sha256": "0" * 64,
                        "text": "const x = 'bad",
                    }
                ],
            }
        )
        self.assertEqual(result["coverage"]["files_parsed"], 0)
        self.assertEqual(result["errors"][0]["code"], "LEX_ERROR")


if __name__ == "__main__":
    unittest.main()
