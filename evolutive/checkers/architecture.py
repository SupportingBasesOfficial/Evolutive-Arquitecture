"""Verificador de referência para regras arquiteturais ainda não automatizadas."""

from __future__ import annotations


CHECKER_ID = "evolutive.architecture.boundaries"
CHECKER_VERSION = "0.1.0"


def check(request: dict) -> dict:
    """Retorna resultado conservador sem inferir conformidade inexistente."""
    files = request["files"]
    return {
        "result_version": 1,
        "checker_id": CHECKER_ID,
        "checker_version": CHECKER_VERSION,
        "outcomes": [
            {
                "rule_id": rule_id,
                "status": "unknown",
                "findings": [],
            }
            for rule_id in request["rule_ids"]
        ],
        "metrics": {
            "files_received": len(files),
            "bytes_received": sum(item["size_bytes"] for item in files),
        },
        "errors": [],
    }
