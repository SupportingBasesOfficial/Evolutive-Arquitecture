from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.architecture_evidence import validate_architecture_evidence
from scripts.content_broker import build_checker_request
from scripts.validate_project_config import DEFAULT_CONFIG

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ArchitectureEvidenceTests(unittest.TestCase):
    def prepare(self, directory: str) -> tuple[Path, Path, dict]:
        root = Path(directory)
        project = root / "consumer"
        (project / ".evolutive").mkdir(parents=True)
        (project / "src" / "core" / "contracts").mkdir(parents=True)
        (project / "src" / "infra").mkdir(parents=True)
        (project / "src" / "infra" / "repo.py").write_text("pass\n", encoding="utf-8")
        (project / "src" / "core" / "contracts" / "repository.py").write_text("pass\n", encoding="utf-8")
        config = project / ".evolutive" / "config.yaml"
        config.write_text(DEFAULT_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
        evidence = {
            "evidence_version": 1,
            "constitution_version": "0.2.0",
            "producer": {"kind": "manual", "id": "architecture-review", "version": "0.1.0"},
            "graph": {
                "components": [
                    {"id": "core", "roots": ["src/core"], "may_depend_on": [], "public_surface": ["src/core/contracts/**"]},
                    {"id": "infra", "roots": ["src/infra"], "may_depend_on": ["core"], "public_surface": []},
                ],
                "dependencies": [
                    {
                        "source_component": "infra",
                        "target_component": "core",
                        "source_path": "src/infra/repo.py",
                        "target_path": "src/core/contracts/repository.py",
                        "kind": "import",
                    }
                ],
            },
        }
        return project, config, evidence

    def write(self, project: Path, evidence: dict) -> None:
        path = project / ".evolutive" / "architecture-evidence.yaml"
        path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")

    def test_accepts_confined_graph(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config, evidence = self.prepare(directory)
            self.write(project, evidence)
            _, failures = validate_architecture_evidence(config, project)
            self.assertEqual(failures, [])

    def test_broker_transports_only_normalized_graph(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config, evidence = self.prepare(directory)
            self.write(project, evidence)
            request, _ = build_checker_request(
                config,
                project,
                REPOSITORY_ROOT / "checkers" / "architecture.yaml",
            )
            self.assertEqual(request["architecture_graph"], evidence["graph"])
            self.assertNotIn("producer", request)
            self.assertNotIn(str(project), str(request["architecture_graph"]))

    def test_rejects_overlapping_component_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config, evidence = self.prepare(directory)
            evidence["graph"]["components"][1]["roots"] = ["src/core/contracts"]
            self.write(project, evidence)
            _, failures = validate_architecture_evidence(config, project)
            self.assertTrue(any("se sobrepõem" in item for item in failures))

    def test_rejects_dependency_path_outside_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config, evidence = self.prepare(directory)
            evidence["graph"]["dependencies"][0]["target_path"] = "src/other/file.py"
            self.write(project, evidence)
            _, failures = validate_architecture_evidence(config, project)
            self.assertTrue(any("target_path fora" in item for item in failures))

    def test_rejects_wildcard_in_concrete_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config, evidence = self.prepare(directory)
            evidence["graph"]["components"][0]["roots"] = ["src/*"]
            self.write(project, evidence)
            _, failures = validate_architecture_evidence(config, project)
            self.assertTrue(any("does not match" in item for item in failures))

    def test_rejects_phantom_dependency_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config, evidence = self.prepare(directory)
            evidence["graph"]["dependencies"][0]["target_path"] = "src/core/contracts/missing.py"
            self.write(project, evidence)
            _, failures = validate_architecture_evidence(config, project)
            self.assertTrue(any("target_path deve ser arquivo regular existente" in item for item in failures))

    def test_rejects_constitution_version_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config, evidence = self.prepare(directory)
            evidence["constitution_version"] = "0.1.0"
            self.write(project, evidence)
            _, failures = validate_architecture_evidence(config, project)
            self.assertTrue(any("constitution_version diverge" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
