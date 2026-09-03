#!/usr/bin/env python3
"""Materializa uma requisição de verificador a partir do escopo autorizado."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

if __package__:
    from .scope_broker import build_inventory
    from .validate_checker_contract import MANIFEST_SCHEMA, validate_manifest
else:
    from scope_broker import build_inventory
    from validate_checker_contract import MANIFEST_SCHEMA, validate_manifest


def extension_allowed(path: str, accepted: list[str]) -> bool:
    return "*" in accepted or Path(path).suffix in accepted


def read_regular_file(project_root: Path, relative: str, limit: int) -> bytes:
    candidate = project_root / relative
    if candidate.is_symlink():
        raise ValueError("link simbólico")

    resolved = candidate.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("caminho escapou da raiz") from exc

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(candidate, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("entrada não é arquivo regular")
        if metadata.st_size > limit:
            raise ValueError("arquivo excede o limite")

        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(descriptor, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > limit:
            raise ValueError("arquivo excede o limite durante a leitura")
        return data
    finally:
        os.close(descriptor)


def build_checker_request(
    config_path: Path,
    project_root: Path,
    manifest_path: Path,
) -> tuple[dict, dict]:
    manifest_failures = validate_manifest(manifest_path)
    if manifest_failures:
        raise ValueError("manifesto inválido: " + "; ".join(manifest_failures))

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors:
        raise ValueError("manifesto inválido")

    project_root = project_root.resolve()
    inventory = build_inventory(config_path, project_root)
    capabilities = manifest["capabilities"]
    accepted = capabilities["file_extensions"]
    limit = capabilities["max_file_bytes"]
    include_text = capabilities["content_access"] == "text"

    files = []
    skipped = []
    bytes_read = 0

    for item in inventory["files"]:
        relative = item["path"]
        if not extension_allowed(relative, accepted):
            skipped.append({"path": relative, "reason": "extension_not_allowed"})
            continue
        try:
            data = read_regular_file(project_root, relative, limit)
        except (OSError, ValueError) as exc:
            skipped.append({"path": relative, "reason": str(exc)})
            continue

        entry = {
            "path": relative,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if include_text:
            try:
                entry["text"] = data.decode("utf-8")
            except UnicodeDecodeError:
                skipped.append({"path": relative, "reason": "not_utf8"})
                continue

        bytes_read += len(data)
        files.append(entry)

    request = {
        "request_version": 1,
        "checker_id": manifest["id"],
        "rule_ids": list(manifest["rules"]),
        "files": files,
    }
    audit = {
        "broker_version": 1,
        "files_considered": len(inventory["files"]),
        "files_delivered": len(files),
        "bytes_read": bytes_read,
        "skipped": skipped,
        "project_root_disclosed": False,
    }
    return request, audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        request, audit = build_checker_request(
            args.config,
            args.project_root,
            args.manifest,
        )
    except (OSError, ValueError, KeyError) as exc:
        print(f"Falha ao materializar requisição: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"request": request, "broker_audit": audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
