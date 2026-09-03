from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_bundle import REPOSITORY_ROOT, build_bundle
from scripts.plan_compliance import build_plan


class CompliancePlanTests(unittest.TestCase):
    def test_planning_verifies_bundle_without_reading_project_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "consumer"
            project.mkdir()
            (project / "src").mkdir()
            sentinel = project / "src" / "must-not-be-read.txt"
            sentinel.write_text("private project content", encoding="utf-8")

            bundle, _ = build_bundle(REPOSITORY_ROOT, "0.1.0", root / "dist")
            config = REPOSITORY_ROOT / "templates" / "project-config.yaml"
            plan = build_plan(config, project, bundle)

            self.assertFalse(plan["inspection"]["performed"])
            self.assertEqual(plan["inspection"]["files_read"], 0)
            self.assertEqual(plan["scope"]["authorized_roots"], ["src", "tests"])
            self.assertNotIn(sentinel.read_text(encoding="utf-8"), str(plan))
            self.assertEqual(
                [rule["id"] for rule in plan["rules"]],
                ["ARCH-001", "ARCH-002", "INT-001", "MOD-001"],
            )
            self.assertTrue(
                all(not rule["eligible_for_enforcement"] for rule in plan["rules"])
            )

    def test_rejects_tampered_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "consumer"
            project.mkdir()
            bundle, _ = build_bundle(REPOSITORY_ROOT, "0.1.0", root / "dist")
            bundle.write_bytes(bundle.read_bytes() + b"tampered")
            config = REPOSITORY_ROOT / "templates" / "project-config.yaml"

            with self.assertRaisesRegex(ValueError, "checksum"):
                build_plan(config, project, bundle)


if __name__ == "__main__":
    unittest.main()
