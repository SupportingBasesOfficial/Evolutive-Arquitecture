"""Registro único de adapters internos autorizados."""

from __future__ import annotations

from pathlib import Path

from .python_imports import adapt as python_imports_adapt

ROOT = Path(__file__).resolve().parent

REGISTRY = {
    "evolutive.adapters.python_imports:adapt": {
        "implementation": python_imports_adapt,
        "path": ROOT / "python_imports.py",
    },
}
