#!/usr/bin/env python3
"""Materializa request limitado para adapter a partir de política e escopo autorizados."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

if __package__:
    from .architecture_policy import load_architecture_policy
    from .content_broker import read_regular_file
    from .scope_broker import build_inventory
    from .validate_adapter_contract import validate_manifest
else:
    from architecture_policy import load_architecture_policy
    from content_broker import read_regular_file
    from scope_broker import build_inventory
    from validate_adapter_contract import validate_manifest


def build_adapter_request(config_path: Path, project_root: Path, manifest_path: Path) -> tuple[dict, dict]:
    failures = validate_manifest(manifest_path)
    if failures:
        raise ValueError("manifesto inválido: " + "; ".join(failures))
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    policy = load_architecture_policy(config_path, project_root)
    inventory = build_inventory(config_path, project_root)
    accepted = set(manifest["capabilities"]["file_extensions"])
    limit = manifest["capabilities"]["max_file_bytes"]

    files: list[dict] = []
    skipped: list[dict] = []
    bytes_read = 0
    root = project_root.resolve()
    for item in inventory["files"]:
        relative = item["path"]
        if Path(relative).suffix not in accepted:
            skipped.append({"path": relative, "reason": "extension_not_allowed"})
            continue
        try:
            data = read_regular_file(root, relative, limit)
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append({"path": relative, "reason": "not_utf8"})
            continue
        except (OSError, ValueError) as exc:
            skipped.append({"path": relative, "reason": str(exc)})
            continue
        files.append({
            "path": relative,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "text": text,
        })
        bytes_read += len(data)

    request = {
        "request_version": 1,
        "adapter_id": manifest["id"],
        "constitution_version": policy["constitution_version"],
        "components": policy["components"],
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        request, audit = build_adapter_request(args.config, args.project_root, args.manifest)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Falha ao materializar request de adapter: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"request": request, "broker_audit": audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
