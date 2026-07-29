"""What one PHP file uses, resolved through the namespaces the repo declares.

PSR-4-AGNOSTIC on purpose: the index is built from the actual `namespace` plus
the class/interface/trait/enum declarations, so it works whatever the folder
layout is — and legacy code whose directories match nothing still resolves.

A trait `use` inside a class body counts. A trait IS a file dependency: the
methods it contributes live in another file, and a reader changing them needs
to know who mixed it in.
"""

from __future__ import annotations

import re

__all__ = ["php_classes", "php_edges", "PhpClasses"]

PhpClasses = dict[str, str]               # fully-qualified name -> relpath

_NAMESPACE = re.compile(r"^\s*namespace\s+([A-Za-z_][\w\\]*)\s*[;{]", re.M)
_DECLARATION = re.compile(
    r"^\s*(?:abstract\s+|final\s+|readonly\s+)*(?:class|interface|trait|enum)\s+"
    r"([A-Za-z_]\w*)", re.M)
# `use A\B\C;` / `use A\B as X;`, top level or inside a class body. `use
# function` and `use const` import callables, not files, and are skipped.
_USE = re.compile(
    r"^\s*use\s+(?!function\b|const\b)([A-Za-z_][\w\\]*)(?:\s+as\s+\w+)?\s*;", re.M)
_USE_GROUP = re.compile(
    r"^\s*use\s+(?!function\b|const\b)([A-Za-z_][\w\\]*)\\\{([^}]+)\}\s*;", re.M)


def php_classes(sources: dict[str, str]) -> PhpClasses:
    """Every declared type's fully-qualified name, mapped to its file."""
    found: PhpClasses = {}
    for relpath, source in sources.items():
        if not relpath.endswith(".php"):
            continue
        match = _NAMESPACE.search(source)
        namespace = match.group(1) if match else ""
        for declaration in _DECLARATION.finditer(source):
            name = declaration.group(1)
            found.setdefault(f"{namespace}\\{name}" if namespace else name, relpath)
    return found


def php_edges(relpath: str, source: str,
              classes: PhpClasses) -> list[tuple[str, str]]:
    match = _NAMESPACE.search(source)
    namespace = match.group(1) if match else ""
    found: set[tuple[str, str]] = set()
    for name in _used_names(source):
        # The file's OWN namespace is tried second, so a bare `use
        # LogsActivity;` inside a class resolves to the sibling trait.
        for candidate in (name, f"{namespace}\\{name}" if namespace else name):
            target = classes.get(candidate)
            if target and target != relpath:
                found.add((target, "import"))
                break
    return sorted(found)


def _used_names(source: str) -> set[str]:
    names = {use.group(1).lstrip("\\") for use in _USE.finditer(source)}
    for group in _USE_GROUP.finditer(source):
        prefix = group.group(1).lstrip("\\")
        for item in group.group(2).split(","):
            leaf = item.strip().split(" as ")[0].strip().lstrip("\\")
            if leaf:
                names.add(f"{prefix}\\{leaf}")
    return names
