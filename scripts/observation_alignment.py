#!/usr/bin/env python3
"""Alinha discovery governado de ecossistemas à observation policy sem alterar outcomes de regra."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

if __package__:
    from .adapter_broker import canonical_sha256
    from .ecosystem_inventory import discover_ecosystems
    from .observation_policy import load_observation_policy
    from .run_adapter import canonical_bytes
else:
    from adapter_broker import canonical_sha256
    from ecosystem_inventory import discover_ecosystems
    from observation_policy import load_observation_policy
    from run_adapter import canonical_bytes

ROOT = Path(__file__).resolve().parents[1]
ALIGNMENT_SCHEMA = ROOT / "schema" / "observation-alignment.schema.json"
ALIGNER_MANIFEST_SCHEMA = ROOT / "schema" / "observation-aligner-manifest.schema.json"
ALIGNER_MANIFEST = ROOT / "governance" / "observation-aligner.yaml"
ALIGNER_ID = "evolutive.observation.aligner"
ALIGNER_VERSION = "0.1.0"


def schema_failures(schema_path: Path, value: object) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return sorted(error.message for error in Draft202012Validator(schema).iter_errors(value))


def validate_aligner_authority() -> dict:
    manifest = yaml.safe_load(ALIGNER_MANIFEST.read_text(encoding="utf-8"))
    failures = schema_failures(ALIGNER_MANIFEST_SCHEMA, manifest)
    if failures:
        raise ValueError("manifesto do observation aligner inválido: " + "; ".join(failures))
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    if manifest["constitution_version"] != version:
        raise ValueError("constitution_version do aligner diverge da Constituição")
    if manifest["id"] != ALIGNER_ID or manifest["version"] != ALIGNER_VERSION:
        raise ValueError("identidade do observation aligner diverge da implementação")
    actual = hashlib.sha256(canonical_bytes(Path(__file__))).hexdigest()
    if manifest["implementation_sha256"] != actual:
        raise ValueError(f"implementation_sha256 do observation aligner diverge: actual={actual}")
    return manifest


def align_observation_policy(config_path: Path, project_root: Path) -> dict:
    aligner = validate_aligner_authority()
    discovered = discover_ecosystems(config_path, project_root)
    policy = load_observation_policy(config_path, project_root)

    required: list[dict] = []
    unsupported: list[str] = []
    for surface in discovered["detected_surfaces"]:
        observation = surface["observation"]
        if observation is None:
            unsupported.append(surface["surface_id"])
        elif observation not in required:
            required.append(observation)

    required.sort(key=lambda item: (item["adapter_id"], item["adapter_version"]))
    declared = sorted(
        [
            {"adapter_id": item["adapter_id"], "adapter_version": item["adapter_version"]}
            for item in policy["required_observations"]
        ],
        key=lambda item: (item["adapter_id"], item["adapter_version"]),
    )
    missing = [item for item in required if item not in declared]
    unsupported.sort()

    reasons: list[str] = []
    if missing:
        reasons.append("missing_required_observation")
    if unsupported:
        reasons.append("unsupported_detected_surface")

    result = {
        "alignment_version": 1,
        "constitution_version": policy["constitution_version"],
        "subject": {
            "inventory_sha256": discovered["subject"]["inventory_sha256"],
            "catalog_sha256": discovered["subject"]["catalog_sha256"],
            "observation_policy_sha256": canonical_sha256(policy),
        },
        "scope": {
            "basis": "governed_ecosystem_catalog",
            "catalog_scope_only": True,
        },
        "evaluator": {
            "id": aligner["id"],
            "version": aligner["version"],
            "implementation_sha256": aligner["implementation_sha256"],
        },
        "evaluation": {
            "verdict": "aligned" if not reasons else "incomplete",
            "required_observations": required,
            "declared_observations": declared,
            "missing_observations": missing,
            "unsupported_surfaces": unsupported,
            "unclassified_files": discovered["unclassified_files"],
            "reasons": reasons,
        },
    }
    failures = schema_failures(ALIGNMENT_SCHEMA, result)
    if failures:
        raise ValueError("observation alignment gerado é inválido: " + "; ".join(failures))
    return result


def validate_alignment(alignment: dict, config_path: Path, project_root: Path) -> list[str]:
    failures = schema_failures(ALIGNMENT_SCHEMA, alignment)
    if failures:
        return failures
    try:
        expected = align_observation_policy(config_path, project_root)
    except (OSError, ValueError, KeyError) as exc:
        return [str(exc)]
    if alignment != expected:
        return ["observation alignment diverge da recomputação determinística do snapshot atual"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--validate", type=Path)
    args = parser.parse_args()
    try:
        if args.validate:
            existing = yaml.safe_load(args.validate.read_text(encoding="utf-8"))
            failures = validate_alignment(existing, args.config, args.project_root)
            if failures:
                raise ValueError("; ".join(failures))
            print("OK: observation alignment corresponde ao snapshot atual.")
            return 0
        result = align_observation_policy(args.config, args.project_root)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(f"Falha no observation alignment: {exc}", file=sys.stderr)
        return 1
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
