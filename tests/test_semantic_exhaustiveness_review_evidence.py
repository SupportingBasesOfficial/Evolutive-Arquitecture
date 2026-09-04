from __future__ import annotations

import copy
import unittest

import yaml

from scripts.validate_semantic_exhaustiveness_review_evidence import (
    EVIDENCE_ROOT,
    _current_subjects,
    expected_path,
    validate_package,
    validate_repository_evidence,
)


class SemanticExhaustivenessReviewEvidenceTests(unittest.TestCase):
    def packages(self) -> list[tuple[str, dict]]:
        result: list[tuple[str, dict]] = []
        for path in sorted(EVIDENCE_ROOT.rglob("*-review.yaml")):
            result.append(
                (
                    path.relative_to(EVIDENCE_ROOT.parents[1]).as_posix(),
                    yaml.safe_load(path.read_text(encoding="utf-8")),
                )
            )
        return result

    def test_current_repository_review_evidence_is_valid(self) -> None:
        self.assertEqual(validate_repository_evidence(), [])

    def test_all_current_packages_are_inconclusive_not_approval(self) -> None:
        packages = self.packages()
        self.assertEqual(len(packages), 3)
        self.assertTrue(
            all(package["conclusion"]["verdict"] == "inconclusive" for _, package in packages)
        )
        self.assertTrue(all(len(package["review"]["methods"]) >= 2 for _, package in packages))

    def test_snapshot_digest_mismatch_is_rejected(self) -> None:
        relative, package = self.packages()[0]
        forged = copy.deepcopy(package)
        if forged["subject"]["kind"] == "taxonomy":
            forged["snapshot"]["relations"][0]["description"] += " changed"
        else:
            forged["snapshot"]["relations"][0]["required"] = False
        failures = validate_package(forged, relative, _current_subjects())
        self.assertTrue(any("semantic_content_sha256" in item for item in failures))

    def test_noncanonical_path_is_rejected(self) -> None:
        _, package = self.packages()[0]
        failures = validate_package(
            package,
            "evidence/semantic-exhaustiveness/manual-review.yaml",
            _current_subjects(),
        )
        self.assertTrue(any("caminho canônico" in item for item in failures))

    def test_stale_snapshot_is_rejected(self) -> None:
        relative, package = self.packages()[0]
        forged = copy.deepcopy(package)
        current = _current_subjects()
        key = (forged["subject"]["kind"], forged["subject"]["id"])
        stale_subjects = copy.deepcopy(current)
        stale_subjects[key] = {**current[key], "constitution_version": "9.9.9"}
        failures = validate_package(forged, relative, stale_subjects)
        self.assertTrue(any("snapshot semântico atual" in item for item in failures))

    def test_supports_established_requires_no_uncertainty(self) -> None:
        relative, package = self.packages()[0]
        forged = copy.deepcopy(package)
        forged["conclusion"]["verdict"] = "supports_established"
        failures = validate_package(forged, relative, _current_subjects())
        self.assertTrue(any("todas as dimensões supported" in item for item in failures))
        self.assertTrue(any("residual_gaps" in item for item in failures))

    def test_supports_established_rejects_self_reference_as_independent_evidence(self) -> None:
        relative, package = self.packages()[0]
        forged = copy.deepcopy(package)
        forged["conclusion"]["verdict"] = "supports_established"
        for dimension in forged["review"]["dimensions"].values():
            dimension["status"] = "supported"
        forged["review"]["residual_gaps"] = []
        for case in forged["review"]["counterexamples"]:
            if case["assessment"] in {"potential_gap", "confirmed_gap"}:
                case["assessment"] = "covered"
        forged["review"]["evidence"] = [
            {
                "kind": "adversarial_review",
                "reference": relative,
                "claim": "The package claims that its own review is sufficient evidence for the positive conclusion.",
            },
            {
                "kind": "normative_analysis",
                "reference": relative + "#self",
                "claim": "A second reference still points back to the same package rather than independent material.",
            },
        ]
        failures = validate_package(forged, relative, _current_subjects())
        self.assertTrue(any("não autorreferentes" in item for item in failures))

    def test_schema_requires_multiple_review_methods(self) -> None:
        relative, package = self.packages()[0]
        forged = copy.deepcopy(package)
        forged["review"]["methods"] = ["single adversarial method only"]
        failures = validate_package(forged, relative, _current_subjects())
        self.assertTrue(failures)

    def test_supports_rejection_requires_negative_evidence(self) -> None:
        relative, package = self.packages()[0]
        forged = copy.deepcopy(package)
        forged["conclusion"]["verdict"] = "supports_rejection"
        failures = validate_package(forged, relative, _current_subjects())
        self.assertTrue(any("confirmed_gap" in item for item in failures))

    def test_unknown_counterexample_relation_is_rejected(self) -> None:
        relative, package = self.packages()[0]
        forged = copy.deepcopy(package)
        forged["review"]["counterexamples"][0]["relation_ids"] = ["not_a_real_relation"]
        failures = validate_package(forged, relative, _current_subjects())
        self.assertTrue(any("relation_ids desconhecidos" in item for item in failures))

    def test_expected_path_is_digest_bound(self) -> None:
        _, package = self.packages()[0]
        self.assertIn(package["subject"]["semantic_content_sha256"], expected_path(package))


if __name__ == "__main__":
    unittest.main()
