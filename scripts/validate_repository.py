#!/usr/bin/env python3
"""Executa o gate canônico antes de integrar ou publicar a Constituição."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from build_bundle import build_bundle
from plan_compliance import build_plan

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
    run([python, "scripts/validate_project_config.py"])
    run([python, "scripts/validate_checker_contract.py"])
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
        bundle, _ = build_bundle(ROOT, version, Path(directory))
        build_plan(ROOT / "templates/project-config.yaml", ROOT, bundle)


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
