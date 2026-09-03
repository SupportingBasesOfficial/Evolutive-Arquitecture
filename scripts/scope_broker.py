#!/usr/bin/env python3
"""Produz um inventário limitado sem ler o conteúdo dos arquivos."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path

import yaml

if __package__:
    from .validate_project_config import DEFAULT_SCHEMA, validate_config
else:
    from validate_project_config import DEFAULT_SCHEMA, validate_config


def matches_exclusion(relative_path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        normalized = pattern.rstrip("/")
        if normalized.endswith("/**"):
            prefix = normalized[:-3].rstrip("/")
            if relative_path == prefix or relative_path.startswith(prefix + "/"):
                return True
        if fnmatch.fnmatchcase(relative_path, normalized):
            return True
    return False


def build_inventory(
    config_path: Path,
    project_root: Path,
    *,
    max_files: int = 10_000,
) -> dict:
    failures = validate_config(config_path, DEFAULT_SCHEMA)
    if failures:
        raise ValueError("configuração inválida: " + "; ".join(failures))
    if max_files < 1:
        raise ValueError("max_files deve ser positivo")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    project_root = project_root.resolve()
    exclusions = config["scope"]["exclude"]

    files: list[dict] = []
    skipped_symlinks: list[str] = []
    missing_roots: list[str] = []

    for configured_root in config["scope"]["roots"]:
        unresolved_root = project_root / configured_root
        if not unresolved_root.exists():
            missing_roots.append(configured_root)
            continue
        if unresolved_root.is_symlink():
            raise ValueError(f"raiz autorizada não pode ser link simbólico: {configured_root}")

        root = unresolved_root.resolve()
        try:
            root.relative_to(project_root)
        except ValueError as exc:
            raise ValueError(f"raiz autorizada escapa do projeto: {configured_root}") from exc

        for candidate in sorted(root.rglob("*")):
            relative = candidate.relative_to(project_root).as_posix()

            if candidate.is_symlink():
                skipped_symlinks.append(relative)
                continue
            if not candidate.is_file() or matches_exclusion(relative, exclusions):
                continue

            resolved = candidate.resolve()
            try:
                resolved.relative_to(project_root)
            except ValueError as exc:
                raise ValueError(f"arquivo escapa do projeto: {relative}") from exc

            files.append({"path": relative, "size_bytes": candidate.stat().st_size})
            if len(files) > max_files:
                raise ValueError(
                    f"limite de {max_files} arquivos excedido; refine scope.roots"
                )

    files.sort(key=lambda item: item["path"])
    skipped_symlinks.sort()
    missing_roots.sort()

    return {
        "inventory_format": 1,
        "authorized_roots": list(config["scope"]["roots"]),
        "excluded_patterns": list(exclusions),
        "files": files,
        "skipped_symlinks": skipped_symlinks,
        "missing_roots": missing_roots,
        "content_access": {
            "performed": False,
            "bytes_read": 0,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--max-files", type=int, default=10_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        inventory = build_inventory(
            args.config,
            args.project_root,
            max_files=args.max_files,
        )
    except (OSError, ValueError, KeyError) as exc:
        print(f"Falha ao construir inventário: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(inventory, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
