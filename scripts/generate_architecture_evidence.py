#!/usr/bin/env python3
"""Executa o caminho seguro policy -> broker -> adapter -> evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

if __package__:
    from .adapter_broker import build_adapter_request
    from .assemble_architecture_evidence import assemble_evidence
    from .run_adapter import execute_adapter
else:
    from adapter_broker import build_adapter_request
    from assemble_architecture_evidence import assemble_evidence
    from run_adapter import execute_adapter


def generate_architecture_evidence(config_path: Path, project_root: Path, manifest_path: Path) -> dict:
    request, broker_audit = build_adapter_request(config_path, project_root, manifest_path)
    result = execute_adapter(manifest_path, request)
    return assemble_evidence(
        config_path,
        project_root,
        manifest_path,
        result,
        broker_audit,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = generate_architecture_evidence(args.config, args.project_root, args.manifest)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Falha ao gerar evidência arquitetural: {exc}", file=sys.stderr)
        return 1
    print(yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
