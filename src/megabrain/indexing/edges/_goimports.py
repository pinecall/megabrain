"""The two Go edge lanes, one function each.

Split from the verb because they answer different questions: an IMPORT lane
resolves a module path to the file defining the name actually used, and a
PACKAGE lane finds the sibling calls Go needs no import for at all.
"""

from __future__ import annotations

import re

from ._gopkg import GoPackages

__all__ = ["import_edges", "sibling_edges"]


def import_edges(relpath: str, stripped: str, alias: str, path: str,
                  key: tuple[str, str] | None,
                  packages: GoPackages) -> set[tuple[str, str]]:
    directory = _import_dir(path, packages)
    if directory is None:
        return set()
    package = packages.primary(directory)
    if package is None or (directory, package) == key:
        return set()
    target = (directory, package)
    found = {(dst, "import") for dst in _used(stripped, alias, package, target,
                                              packages) if dst != relpath}
    if found:
        return found
    # A dot/blank import, or no use this pass could attribute: edge to the
    # package's representative file rather than drop a real dependency.
    leaf = path.rsplit("/", 1)[-1] + ".go"
    candidates = packages.files.get(target, [])
    named = f"{directory}/{leaf}" if directory else leaf
    fallback = named if named in candidates else (candidates[0] if candidates else None)
    return {(fallback, "import")} if fallback and fallback != relpath else set()


def _used(stripped: str, alias: str, package: str, target: tuple[str, str],
          packages: GoPackages) -> set[str]:
    if alias in (".", "_"):
        return set()
    name = alias or package
    uses = re.compile(rf"(?<![.\w]){re.escape(name)}\.([A-Za-z_]\w*)")
    declares = packages.declares.get(target, {})
    return {dst for match in uses.finditer(stripped)
            if (dst := declares.get(match.group(1)))}


def sibling_edges(relpath: str, stripped: str, key: tuple[str, str],
                   packages: GoPackages) -> set[tuple[str, str]]:
    siblings = {name: file for name, file in packages.declares.get(key, {}).items()
                if file != relpath and len(name) >= 2}
    if not siblings:
        return set()
    uses = re.compile(r"(?<![.\w])(" + "|".join(map(re.escape, sorted(siblings)))
                      + r")\b")
    return {(siblings[match.group(1)], "call") for match in uses.finditer(stripped)}


def _import_dir(path: str, packages: GoPackages) -> str | None:
    """An import path to a repo directory.

    `go.mod` is not indexed, so the module prefix is unknown: strip leading
    segments until the remainder IS a repo directory holding Go files. The
    module root itself has no such suffix — resolve it by package name
    instead, and only for dotted (domain-style) module paths, so a stdlib
    `import "log"` can never hit a repo package by accident.
    """
    segments = path.split("/")
    for cut in range(1, len(segments)):
        candidate = "/".join(segments[cut:])
        if candidate in packages.packages_in:
            return candidate
    if len(segments) >= 3 and "." in segments[0]:
        hits = [d for d in packages.packages_in
                if packages.primary(d) == segments[-1]]
        if len(hits) == 1:
            return hits[0]
    return None
