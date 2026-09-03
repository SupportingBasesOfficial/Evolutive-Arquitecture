"""Adapter conservador para dependências estáticas/locais TypeScript e JavaScript."""

from __future__ import annotations

import posixpath
from pathlib import PurePosixPath

ADAPTER_ID = "evolutive.ecmascript.imports"
ADAPTER_VERSION = "0.1.0"
ECOSYSTEM = "ecmascript"
SUPPORTED_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs")
REGEX_PREFIX_IDENTIFIERS = {
    "return",
    "throw",
    "case",
    "delete",
    "void",
    "typeof",
    "instanceof",
    "in",
    "of",
    "yield",
    "await",
}
REGEX_PREFIX_PUNCT = set("({[=,:;!&|?+-*%^~<>")


def within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def component_for(path: str, components: list[dict]) -> str | None:
    matches = [
        component["id"]
        for component in components
        if any(within(path, root) for root in component["roots"])
    ]
    return matches[0] if len(matches) == 1 else None


def regex_may_start(tokens: list[tuple[str, str]]) -> bool:
    if not tokens:
        return True
    kind, value = tokens[-1]
    if kind == "identifier":
        return value in REGEX_PREFIX_IDENTIFIERS
    return kind == "punct" and value in REGEX_PREFIX_PUNCT


def skip_regex_literal(text: str, index: int) -> tuple[int | None, str | None]:
    """Avança sobre regex literal conservador, incluindo character classes e flags."""
    cursor = index + 1
    in_class = False
    while cursor < len(text):
        current = text[cursor]
        if current in "\r\n":
            return None, "regex literal não terminado antes da quebra de linha"
        if current == "\\":
            cursor += 2
            continue
        if current == "[":
            in_class = True
            cursor += 1
            continue
        if current == "]" and in_class:
            in_class = False
            cursor += 1
            continue
        if current == "/" and not in_class:
            cursor += 1
            while cursor < len(text) and text[cursor].isalpha():
                cursor += 1
            return cursor, None
        cursor += 1
    return None, "regex literal não terminado"


def lex_module_tokens(text: str) -> tuple[list[tuple[str, str]], str | None]:
    """Tokeniza somente o necessário para reconhecer module specifiers sem executar JS."""
    tokens: list[tuple[str, str]] = []
    index = 0
    length = len(text)

    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue

        if text.startswith("//", index):
            newline = text.find("\n", index + 2)
            index = length if newline < 0 else newline + 1
            continue

        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                return tokens, "comentário de bloco não terminado"
            index = end + 2
            continue

        if char == "/" and regex_may_start(tokens):
            next_index, error = skip_regex_literal(text, index)
            if error:
                return tokens, error
            tokens.append(("regex", ""))
            index = next_index if next_index is not None else length
            continue

        if char in ("'", '"'):
            quote = char
            index += 1
            value: list[str] = []
            while index < length:
                current = text[index]
                if current == "\\":
                    if index + 1 >= length:
                        return tokens, "escape não terminado em string"
                    value.append(text[index + 1])
                    index += 2
                    continue
                if current == quote:
                    tokens.append(("string", "".join(value)))
                    index += 1
                    break
                if current in "\r\n":
                    return tokens, "string não terminada antes da quebra de linha"
                value.append(current)
                index += 1
            else:
                return tokens, "string não terminada"
            continue

        if char == "`":
            index += 1
            while index < length:
                current = text[index]
                if current == "\\":
                    index += 2
                    continue
                if text.startswith("${", index):
                    return tokens, "template literal interpolado não é analisado com segurança"
                if current == "`":
                    index += 1
                    break
                index += 1
            else:
                return tokens, "template literal não terminado"
            tokens.append(("template", ""))
            continue

        if char.isalpha() or char in "_$":
            start = index
            index += 1
            while index < length and (text[index].isalnum() or text[index] in "_$"):
                index += 1
            tokens.append(("identifier", text[start:index]))
            continue

        tokens.append(("punct", char))
        index += 1

    return tokens, None


def is_property_access(tokens: list[tuple[str, str]], index: int) -> bool:
    return index > 0 and tokens[index - 1] == ("punct", ".")


def find_from_specifier(tokens: list[tuple[str, str]], start: int) -> tuple[str | None, int]:
    depth = 0
    cursor = start
    while cursor < len(tokens):
        token = tokens[cursor]
        if token == ("punct", ";") and depth == 0:
            return None, cursor + 1
        if token[0] == "punct" and token[1] in "({[":
            depth += 1
        elif token[0] == "punct" and token[1] in ")}]":
            depth = max(0, depth - 1)
        elif depth == 0 and token == ("identifier", "from"):
            if cursor + 1 < len(tokens) and tokens[cursor + 1][0] == "string":
                return tokens[cursor + 1][1], cursor + 2
            return None, cursor + 1
        cursor += 1
    return None, cursor


def module_specifiers(tokens: list[tuple[str, str]]) -> list[str]:
    """Extrai apenas module specifiers ECMAScript de alta confiança."""
    result: list[str] = []
    index = 0

    while index < len(tokens):
        kind, value = tokens[index]
        if kind != "identifier" or is_property_access(tokens, index):
            index += 1
            continue

        if value == "import":
            if index + 1 < len(tokens) and tokens[index + 1] == ("punct", "."):
                index += 2
                continue
            if index + 1 < len(tokens) and tokens[index + 1][0] == "string":
                result.append(tokens[index + 1][1])
                index += 2
                continue
            if (
                index + 2 < len(tokens)
                and tokens[index + 1] == ("punct", "(")
                and tokens[index + 2][0] == "string"
            ):
                result.append(tokens[index + 2][1])
                index += 3
                continue
            specifier, next_index = find_from_specifier(tokens, index + 1)
            if specifier is not None:
                result.append(specifier)
            index = next_index
            continue

        if value == "export":
            specifier, next_index = find_from_specifier(tokens, index + 1)
            if specifier is not None:
                result.append(specifier)
            index = next_index
            continue

        index += 1

    return result


def normalized_relative(source_path: str, specifier: str) -> str | None:
    if not (specifier.startswith("./") or specifier.startswith("../")):
        return None
    base = PurePosixPath(source_path).parent.as_posix()
    candidate = posixpath.normpath(posixpath.join(base, specifier))
    if candidate == ".." or candidate.startswith("../") or candidate.startswith("/"):
        return None
    return candidate


def resolve_relative(source_path: str, specifier: str, known_files: set[str]) -> str | None:
    base = normalized_relative(source_path, specifier)
    if base is None:
        return None

    candidates: list[str] = []
    suffix = PurePosixPath(base).suffix
    if suffix:
        if base in known_files:
            candidates.append(base)
    else:
        for extension in SUPPORTED_EXTENSIONS:
            direct = base + extension
            if direct in known_files:
                candidates.append(direct)
        for extension in SUPPORTED_EXTENSIONS:
            indexed = base.rstrip("/") + "/index" + extension
            if indexed in known_files:
                candidates.append(indexed)

    unique = sorted(set(candidates))
    return unique[0] if len(unique) == 1 else None


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
    known_files = {item["path"] for item in files}
    path_component = {
        path: owner
        for path in known_files
        if (owner := component_for(path, components)) is not None
    }

    dependencies: list[dict] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    errors: list[dict] = []
    analyzed = 0
    unresolved = 0

    for item in files:
        source_path = item["path"]
        tokens, lexical_error = lex_module_tokens(item["text"])
        if lexical_error:
            errors.append({
                "code": "LEX_ERROR",
                "path": source_path,
                "message": lexical_error,
            })
            continue
        analyzed += 1

        for specifier in module_specifiers(tokens):
            if not (specifier.startswith("./") or specifier.startswith("../")):
                unresolved += 1
                continue
            target_path = resolve_relative(source_path, specifier, known_files)
            if target_path is None:
                unresolved += 1
                continue
            edge = dependency(source_path, target_path, path_component)
            if edge is None:
                continue
            identity = tuple(
                edge[key]
                for key in (
                    "source_component",
                    "target_component",
                    "source_path",
                    "target_path",
                    "kind",
                )
            )
            if identity not in seen:
                seen.add(identity)
                dependencies.append(edge)

    dependencies.sort(
        key=lambda item: (
            item["source_path"],
            item["target_path"],
            item["source_component"],
            item["target_component"],
        )
    )
    return {
        "result_version": 1,
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "ecosystem": ECOSYSTEM,
        "dependencies": dependencies,
        "coverage": {
            "files_received": len(files),
            "files_parsed": analyzed,
            "bytes_received": sum(item["size_bytes"] for item in files),
            "unresolved_references": unresolved,
        },
        "errors": errors,
    }
