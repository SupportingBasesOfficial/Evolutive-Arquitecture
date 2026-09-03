"""Registro único de adapters internos autorizados."""

from __future__ import annotations

from pathlib import Path

from .ecmascript_imports import adapt as ecmascript_imports_adapt
from .python_imports import adapt as python_imports_adapt

ROOT = Path(__file__).resolve().parent

REGISTRY = {
    "evolutive.adapters.python_imports:adapt": {
        "implementation": python_imports_adapt,
        "path": ROOT / "python_imports.py",
    },
    "evolutive.adapters.ecmascript_imports:adapt": {
        "implementation": ecmascript_imports_adapt,
        "path": ROOT / "ecmascript_imports.py",
    },
}
