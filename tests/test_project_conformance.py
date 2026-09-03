from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.build_bundle import REPOSITORY_ROOT, build_bundle
from scripts.check_project import run_conformance
from scripts.validate_project_config import DEFAULT_CONFIG


class ProjectConformanceTests(unittest.TestCase):
    def prepare(self, directory: str) -> tuple[Path, Path, Path]:
        root = Path(directory)
        project = root / "consumer"
        (project / "src").mkdir(parents=True)
        (project / "tests").mkdir()
        (project / ".evolutive").mkdir()
        (project / "src" / "app.py").write_text("answer = 42\n", encoding="utf-8")

        bundle, _ = build_bundle(REPOSITORY_ROOT, "0.1.0", root / "dist")
        config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        config["constitution"]["sha256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
        config_path = project / ".evolutive" / "config.yaml"
        config_path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return project, config_path, bundle

    def test_connects_pipeline_without_disclosing_root_to_checker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, config, bundle = self.prepare(directory)
            report = run_conformance(
                config,
                project,
                bundle,
                REPOSITORY_ROOT / "templates" / "checker-manifest.yaml",
            )

            self.assertTrue(report["isolation"]["producer_consumer_trees_disjoint"])
            self.assertFalse(report["isolation"]["project_root_disclosed_to_checker"])
            self.assertTrue(report["isolation"]["checker_received_only_brokered_files"])
            self.assertEqual(report["broker_audit"]["files_delivered"], 1)
            self.assertEqual(
                {item["status"] for item in report["checker_result"]["outcomes"]},
                {"unknown"},
            )
            self.assertNotIn(str(project), str(report["checker_result"]))

    def test_refuses_to_validate_constitution_repository_itself(self) -> None:
        with self.assertRaisesRegex(ValueError, "árvores de diretórios separadas"):
            run_conformance(
                REPOSITORY_ROOT / "templates" / "project-config.yaml",
                REPOSITORY_ROOT,
                REPOSITORY_ROOT / "unused.zip",
                REPOSITORY_ROOT / "templates" / "checker-manifest.yaml",
            )

    def test_refuses_nested_producer_and_consumer_trees(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            producer = root / "producer"
            consumer = producer / "consumer"
            consumer.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "árvores de diretórios separadas"):
                run_conformance(
                    root / "unused.yaml",
                    consumer,
                    root / "unused.zip",
                    root / "unused-manifest.yaml",
                    constitution_root=producer,
                )


if __name__ == "__main__":
    unittest.main()
