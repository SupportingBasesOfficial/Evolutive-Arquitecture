#!/usr/bin/env python3
"""Produz um bundle determinístico e seu checksum SHA-256."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_files(root: Path) -> list[Path]:
    required = [
        root / "META-CONSTITUTION.md",
        root / "schema" / "rule.schema.json",
    ]
    rules = sorted((root / "rules").rglob("*.yaml"))
    paths = required + rules
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(", ".join(str(path) for path in missing))
    if not rules:
        raise ValueError("Nenhuma regra encontrada para empacotar.")
    return paths


def write_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


def build_bundle(root: Path, version: str, output_dir: Path) -> tuple[Path, Path]:
    root = root.resolve()
    output_dir = output_dir.resolve()

    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Versão semântica inválida: {version}")

    files: list[tuple[str, bytes]] = []
    for path in source_files(root):
        name = path.relative_to(root).as_posix()
        files.append((name, path.read_bytes()))

    manifest = {
        "format_version": 1,
        "constitution_version": version,
        "files": [
            {"path": name, "sha256": digest(data)}
            for name, data in files
        ],
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"evolutive-architecture-{version}.zip"

    with zipfile.ZipFile(archive_path, "w") as archive:
        write_entry(archive, "manifest.json", manifest_bytes)
        for name, data in files:
            write_entry(archive, name, data)

    checksum_path = archive_path.with_suffix(".zip.sha256")
    checksum_path.write_text(
        f"{digest(archive_path.read_bytes())}  {archive_path.name}\n",
        encoding="ascii",
    )
    return archive_path, checksum_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive, checksum = build_bundle(REPOSITORY_ROOT, args.version, args.output_dir)
    print(archive)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
