"""The TypeScript/JavaScript import graph.

Regex over the import forms rather than another tree walk: the shapes are few
and unambiguous at the start of a line, and the graph only needs the SPECIFIER —
which module a file pulls from — not what it took from it.

Resolution is the real work. `./thing` in TypeScript means any of six files
(`thing.ts`, `thing.tsx`, `thing/index.ts`, …), the extension is usually
omitted, and `.js` in an ESM import routinely means the `.ts` beside it. Getting
that wrong does not fail — it silently yields a repository with no edges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

__all__ = ["TsFiles", "ts_files", "ts_edges"]

# `import x from "m"` · `import "m"` · `export … from "m"` · `require("m")` ·
# `import("m")`. The quote style is either, and the specifier is group 1 or 2.
_SPECIFIER = re.compile(
    r"""(?:^|\s|[=({,])(?:import|export)\s[^;'"]*?from\s*['"]([^'"]+)['"]"""
    r"""|(?:^|\s)import\s*['"]([^'"]+)['"]"""
    r"""|(?:require|import)\s*\(\s*['"]([^'"]+)['"]\s*\)""",
    re.MULTILINE)

_EXTENSIONS = (".ts", ".tsx", ".d.ts", ".js", ".jsx", ".mjs", ".cjs", ".vue")
_INDEXES = tuple(f"/index{ext}" for ext in _EXTENSIONS)


@dataclass(frozen=True, slots=True)
class TsFiles:
    """Every indexed path, which is all relative-import resolution needs."""

    paths: frozenset[str]


def ts_files(sources: dict[str, str]) -> TsFiles:
    return TsFiles(frozenset(sources))


def ts_edges(relpath: str, source: str, context: TsFiles) -> list[tuple[str, str]]:
    """(target, kind) for every in-repo import. Bare specifiers are packages.

    An unresolvable specifier is DROPPED rather than guessed at: `react` is not
    a file in this repository, and inventing an edge to something that merely
    shares a name is worse than the missing edge.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in _SPECIFIER.finditer(source):
        specifier = match.group(1) or match.group(2) or match.group(3)
        if not specifier or not specifier.startswith("."):
            continue                   # a package, not a file in this repo
        target = _resolve(relpath, specifier, context.paths)
        if target is not None and target != relpath and target not in seen:
            seen.add(target)
            found.append((target, "import"))
    return found


def _resolve(relpath: str, specifier: str, paths: frozenset[str]) -> str | None:
    base = (PurePosixPath(relpath).parent / specifier)
    candidate = _normalise(base)
    for guess in _candidates(candidate):
        if guess in paths:
            return guess
    return None


def _candidates(candidate: str) -> list[str]:
    """Every file the specifier could mean, most exact first.

    The `.js` -> `.ts` rewrite is not a nicety: ESM requires the extension in
    the import, TypeScript compiles `.ts` to `.js`, so a correctly written
    TypeScript project imports `./thing.js` and MEANS `./thing.ts`. Without
    this, a modern repo yields almost no edges at all.
    """
    if candidate.endswith((".js", ".mjs", ".cjs")):
        stem = candidate.rsplit(".", 1)[0]
        return [candidate, f"{stem}.ts", f"{stem}.tsx", f"{stem}.d.ts",
                *(f"{stem}{index}" for index in _INDEXES)]
    return [candidate, *(f"{candidate}{ext}" for ext in _EXTENSIONS),
            *(f"{candidate}{index}" for index in _INDEXES)]


def _normalise(path: PurePosixPath) -> str:
    """Collapse `..` and `.` textually — the path need not exist on disk, and
    `Path.resolve()` would anchor it to the machine's filesystem instead of the
    repository."""
    parts: list[str] = []
    for part in path.parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part not in (".", ""):
            parts.append(part)
    return "/".join(parts)
