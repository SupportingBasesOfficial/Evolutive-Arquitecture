"""Adapter de referência que observa imports Python locais via AST."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import PurePosixPath

ADAPTER_ID = "evolutive.python.imports"
ADAPTER_VERSION = "0.1.0"
ECOSYSTEM = "python"


def within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def component_for(path: str, components: list[dict]) -> str | None:
    matches = [item["id"] for item in components if any(within(path, root) for root in item["roots"])]
    return matches[0] if len(matches) == 1 else None


def module_name(path: str, anchor: PurePosixPath) -> str | None:
    candidate = PurePosixPath(path)
    try:
        relative = candidate.relative_to(anchor)
    except ValueError:
        return None
    parts = list(relative.parts)
    if not parts or not parts[-1].endswith(".py"):
        return None
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(part for part in parts if part)


def build_module_index(files: list[dict], components: list[dict]) -> tuple[dict[str, set[str]], dict[str, str], set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    path_component: dict[str, str] = {}
    local_tops: set[str] = set()
    for item in files:
        path = item["path"]
        owner = component_for(path, components)
        if owner is None:
            continue
        path_component[path] = owner
        component = next(component for component in components if component["id"] == owner)
        for root in component["roots"]:
            if not within(path, root):
                continue
            for anchor in (PurePosixPath(root), PurePosixPath(root).parent):
                name = module_name(path, anchor)
                if name:
                    index[name].add(path)
                    local_tops.add(name.split(".", 1)[0])
    return index, path_component, local_tops


def source_package(path: str, index: dict[str, set[str]]) -> str | None:
    candidates = [name for name, paths in index.items() if path in paths]
    if not candidates:
        return None
    name = max(candidates, key=lambda item: item.count("."))
    if path.endswith("/__init__.py"):
        return name
    return name.rpartition(".")[0]


def resolve(name: str, index: dict[str, set[str]]) -> str | None:
    paths = index.get(name, set())
    return next(iter(paths)) if len(paths) == 1 else None


def resolve_from(module: str, imported: str, index: dict[str, set[str]]) -> str | None:
    combined = f"{module}.{imported}" if module else imported
    target = resolve(combined, index)
    if target:
        return target
    return resolve(module, index) if module else None


def relative_module(package: str | None, level: int, module: str | None) -> str | None:
    if package is None:
        return None
    parts = package.split(".") if package else []
    ascend = level - 1
    if ascend > len(parts):
        return None
    base = parts[: len(parts) - ascend] if ascend else parts
    if module:
        base.extend(module.split("."))
    return ".".join(base)


def dependency(source_path: str, target_path: str, path_component: dict[str, str]) -> dict | None:
    source = path_component.get(source_path)
    target = path_component.get(target_path)
    if source is None or target is None or source == target:
        return None
    return {
        "source_component": source,
        "target_component": target,
        "source_path": source_path,
        "target_path": target_path,
        "kind": "import",
    }


def adapt(request: dict) -> dict:
    files = request["files"]
    components = request["components"]
    index, path_component, local_tops = build_module_index(files, components)
    dependencies: list[dict] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    errors: list[dict] = []
    parsed = 0
    unresolved = 0

    for item in files:
        source_path = item["path"]
        try:
            tree = ast.parse(item["text"], filename=source_path)
        except SyntaxError as exc:
            errors.append({"code": "PARSE_ERROR", "path": source_path, "message": str(exc)})
            continue
        parsed += 1
        package = source_package(source_path, index)

        for node in ast.walk(tree):
            targets: list[str | None] = []
            expected_local = False
            if isinstance(node, ast.Import):
                for alias in node.names:
                    targets.append(resolve(alias.name, index))
                    expected_local = expected_local or alias.name.split(".", 1)[0] in local_tops
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = relative_module(package, node.level, node.module)
                    expected_local = True
                else:
                    base = node.module or ""
                    expected_local = bool(base and base.split(".", 1)[0] in local_tops)
                for alias in node.names:
                    if alias.name == "*":
                        targets.append(resolve(base, index) if base else None)
                    else:
                        targets.append(resolve_from(base or "", alias.name, index))
            else:
                continue

            for target_path in targets:
                if target_path is None:
                    if expected_local:
                        unresolved += 1
                    continue
                edge = dependency(source_path, target_path, path_component)
                if edge is None:
                    continue
                identity = tuple(edge[key] for key in ("source_component", "target_component", "source_path", "target_path", "kind"))
                if identity not in seen:
                    seen.add(identity)
                    dependencies.append(edge)

    dependencies.sort(key=lambda item: (item["source_path"], item["target_path"], item["source_component"], item["target_component"]))
    return {
        "result_version": 1,
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "ecosystem": ECOSYSTEM,
        "dependencies": dependencies,
        "coverage": {
            "files_received": len(files),
            "files_parsed": parsed,
            "bytes_received": sum(item["size_bytes"] for item in files),
            "unresolved_references": unresolved,
        },
        "errors": errors,
    }
