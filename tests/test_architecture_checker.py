from __future__ import annotations

import unittest

from evolutive.checkers.architecture import check


class ArchitectureCheckerTests(unittest.TestCase):
    def request(self, graph: dict) -> dict:
        return {
            "request_version": 1,
            "checker_id": "evolutive.architecture.boundaries",
            "rule_ids": ["ARCH-001", "ARCH-002", "MOD-001", "INT-001"],
            "files": [],
            "architecture_graph": graph,
        }

    def test_detects_forbidden_direction_and_internal_surface_access(self) -> None:
        graph = {
            "components": [
                {
                    "id": "core",
                    "roots": ["src/core"],
                    "may_depend_on": [],
                    "public_surface": ["src/core/contracts/**"],
                },
                {
                    "id": "infra",
                    "roots": ["src/infra"],
                    "may_depend_on": [],
                    "public_surface": [],
                },
            ],
            "dependencies": [
                {
                    "source_component": "infra",
                    "target_component": "core",
                    "source_path": "src/infra/repo.py",
                    "target_path": "src/core/internal/model.py",
                    "kind": "import",
                }
            ],
        }
        result = check(self.request(graph))
        outcomes = {item["rule_id"]: item for item in result["outcomes"]}
        self.assertEqual(outcomes["ARCH-002"]["status"], "fail")
        self.assertEqual(outcomes["MOD-001"]["status"], "fail")
        self.assertEqual(outcomes["ARCH-001"]["status"], "unknown")
        self.assertEqual(outcomes["INT-001"]["status"], "unknown")
        self.assertRegex(outcomes["ARCH-002"]["findings"][0]["fingerprint"], r"^[a-f0-9]{64}$")

    def test_valid_observation_remains_unknown_not_pass(self) -> None:
        graph = {
            "components": [
                {
                    "id": "core",
                    "roots": ["src/core"],
                    "may_depend_on": [],
                    "public_surface": ["src/core/contracts/**"],
                },
                {
                    "id": "infra",
                    "roots": ["src/infra"],
                    "may_depend_on": ["core"],
                    "public_surface": [],
                },
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
        }
        result = check(self.request(graph))
        self.assertTrue(all(item["status"] == "unknown" for item in result["outcomes"]))


if __name__ == "__main__":
    unittest.main()
