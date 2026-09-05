#!/usr/bin/env python3
"""Executa o gate canônico antes de integrar ou publicar a Constituição."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from build_bundle import build_bundle
from plan_compliance import build_plan
from validate_project_exceptions import validate_project_exceptions

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode:
        raise RuntimeError(
            f"gate interrompido com código {completed.returncode}: "
            + " ".join(command)
        )


def validate_repository() -> None:
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    python = sys.executable

    run([python, "-m", "unittest", "discover", "--start-directory", "tests"])
    run([python, "scripts/validate_rules.py"])
    run([python, "scripts/validate_rule_lifecycle.py", "--version", version])
    run([python, "scripts/validate_rule_readiness.py"])
    run([python, "scripts/validate_repository_governance.py"])
    run([python, "scripts/validate_project_config.py"])
    run([python, "scripts/validate_checker_contract.py"])
    run([python, "scripts/validate_adapter_contract.py"])
    run([python, "scripts/validate_coverage_attestation_contract.py"])
    run([python, "scripts/validate_coverage_composition_contract.py"])
    run([python, "scripts/validate_ecosystem_discovery_contract.py"])
    run([python, "scripts/validate_result_aggregation_contract.py"])
    run([python, "scripts/validate_rule_semantic_coverage_contract.py"])
    run([python, "scripts/validate_semantic_exhaustiveness_governance.py"])
    run([python, "scripts/validate_semantic_exhaustiveness_review_evidence.py"])
    run([python, "scripts/validate_build_time_provenance_governance.py"])
    run([python, "scripts/validate_provenance_producer_contract.py"])
    run([python, "scripts/validate_provenance_semantic_interpretation_contract.py"])
    run([python, "scripts/validate_semantic_relation_evidence_aggregation.py"])
    run([python, "scripts/validate_relation_observation_scope_attestation.py"])
    run([python, "scripts/validate_relation_surface_inventory_attestation.py"])
    run([python, "scripts/validate_relation_surface_discovery.py"])
    run(
        [
            python,
            "scripts/run_checker.py",
            "templates/checker-request.json",
            "--manifest",
            "templates/checker-manifest.yaml",
        ]
    )

    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        bundle, _ = build_bundle(ROOT, version, temporary)
        build_plan(ROOT / "templates/project-config.yaml", ROOT, bundle)

        consumer = temporary / "consumer"
        consumer.mkdir()
        exception_failures = validate_project_exceptions(
            ROOT / "templates/project-config.yaml",
            consumer,
            bundle,
        )
        if exception_failures:
            raise ValueError(
                "contrato de exceções inválido: " + "; ".join(exception_failures)
            )


def main() -> int:
    try:
        validate_repository()
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"Falha no gate canônico: {exc}", file=sys.stderr)
        return 1

    print("OK: gate canônico de integração e publicação concluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
