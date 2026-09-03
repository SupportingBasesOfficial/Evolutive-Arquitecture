"""Verificador de referência para regras arquiteturais experimentais."""

from __future__ import annotations

import fnmatch
import hashlib
import json


CHECKER_ID = "evolutive.architecture.boundaries"
CHECKER_VERSION = "0.2.0"


def fingerprint(rule_id: str, dependency: dict, reason: str) -> str:
    payload = {
        "rule_id": rule_id,
        "dependency": dependency,
        "reason": reason,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def finding(rule_id: str, dependency: dict, message: str, reason: str) -> dict:
    return {
        "path": dependency["source_path"],
        "message": message,
        "fingerprint": fingerprint(rule_id, dependency, reason),
    }


def target_is_public(component: dict, target_path: str) -> bool:
    return any(
        fnmatch.fnmatchcase(target_path, pattern)
        for pattern in component["public_surface"]
    )


def evaluate_architecture(graph: dict | None) -> dict[str, list[dict]]:
    findings = {"ARCH-002": [], "MOD-001": []}
    if graph is None:
        return findings

    components = {component["id"]: component for component in graph["components"]}
    for dependency in graph["dependencies"]:
        source_id = dependency["source_component"]
        target_id = dependency["target_component"]
        if source_id == target_id:
            continue

        source = components[source_id]
        target = components[target_id]

        if target_id not in source["may_depend_on"]:
            findings["ARCH-002"].append(
                finding(
                    "ARCH-002",
                    dependency,
                    (
                        f"{source_id} depende de {target_id}, mas essa direção não "
                        "está autorizada no modelo arquitetural."
                    ),
                    "dependency-direction",
                )
            )

        if not target_is_public(target, dependency["target_path"]):
            findings["MOD-001"].append(
                finding(
                    "MOD-001",
                    dependency,
                    (
                        f"{source_id} acessa {dependency['target_path']} de {target_id}, "
                        "fora da superfície pública declarada."
                    ),
                    "internal-surface-access",
                )
            )

    return findings


def check(request: dict) -> dict:
    """Detecta violações comprováveis sem inferir conformidade pela ausência delas."""
    files = request["files"]
    detected = evaluate_architecture(request.get("architecture_graph"))

    outcomes = []
    for rule_id in request["rule_ids"]:
        rule_findings = detected.get(rule_id, [])
        outcomes.append(
            {
                "rule_id": rule_id,
                "status": "fail" if rule_findings else "unknown",
                "findings": rule_findings,
            }
        )

    return {
        "result_version": 1,
        "checker_id": CHECKER_ID,
        "checker_version": CHECKER_VERSION,
        "outcomes": outcomes,
        "metrics": {
            "files_received": len(files),
            "bytes_received": sum(item["size_bytes"] for item in files),
        },
        "errors": [],
    }
