#!/usr/bin/env python3
"""Verifica a fonte constitucional e produz um plano sem inspecionar código."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import yaml

from validate_project_config import DEFAULT_SCHEMA, validate_config


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_verified_bundle(bundle_path: Path, expected_digest: str, version: str) -> dict:
    bundle_bytes = bundle_path.read_bytes()
    actual_digest = sha256(bundle_bytes)
    if actual_digest != expected_digest:
        raise ValueError(
            f"checksum do bundle divergente: esperado {expected_digest}, "
            f"obtido {actual_digest}"
        )

    with zipfile.ZipFile(bundle_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("constitution_version") != version:
            raise ValueError("versão do manifesto não corresponde à configuração")

        declared = manifest.get("files")
        if not isinstance(declared, list):
            raise ValueError("manifesto não contém uma lista de arquivos")

        for item in declared:
            data = archive.read(item["path"])
            if sha256(data) != item["sha256"]:
                raise ValueError(f"arquivo interno adulterado: {item['path']}")

        rules = []
        for item in declared:
            name = item["path"]
            if name.startswith("rules/") and name.endswith(".yaml"):
                rule = yaml.safe_load(archive.read(name))
                rules.append(rule)

    return {"manifest": manifest, "rules": rules}


def build_plan(config_path: Path, project_root: Path, bundle_path: Path) -> dict:
    failures = validate_config(config_path, DEFAULT_SCHEMA)
    if failures:
        raise ValueError("configuração inválida: " + "; ".join(failures))

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    source = load_verified_bundle(
        bundle_path,
        config["constitution"]["sha256"],
        config["constitution"]["version"],
    )

    unsupported = [item for item in config["profiles"] if item != "universal"]
    if unsupported:
        raise ValueError(
            "perfis ainda não disponíveis: " + ", ".join(sorted(unsupported))
        )

    project_root = project_root.resolve()
    authorized_roots = []
    for relative in config["scope"]["roots"]:
        candidate = (project_root / relative).resolve()
        try:
            candidate.relative_to(project_root)
        except ValueError as exc:
            raise ValueError(f"raiz escapa do projeto: {relative}") from exc
        authorized_roots.append(relative)

    selected_rules = [
        {
            "id": rule["id"],
            "status": rule["status"],
            "enforcement_level": rule["enforcement"]["level"],
            "eligible_for_enforcement": rule["status"] == "active",
        }
        for rule in source["rules"]
        if rule["layer"] == "universal"
    ]

    return {
        "plan_format": 1,
        "constitution": {
            "version": config["constitution"]["version"],
            "bundle_sha256": config["constitution"]["sha256"],
        },
        "mode": config["mode"],
        "scope": {
            "project_root": str(project_root),
            "authorized_roots": authorized_roots,
            "excluded": config["scope"]["exclude"],
        },
        "rules": sorted(selected_rules, key=lambda item: item["id"]),
        "inspection": {
            "performed": False,
            "files_read": 0,
            "reason": "planning stage only",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        plan = build_plan(args.config, args.project_root, args.bundle)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"Falha ao criar plano: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
