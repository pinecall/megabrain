"""What one Python file DEPENDS ON: import and call edges.

The rule the whole extractor rests on: **a call edge exists only through a
resolved import.** A cross-file Python call that was never imported cannot
execute, so a bare-name match is not evidence — matching names across files
mints phantoms out of coincidence (`re.search` pointing at the repo's own
`search()`), and a phantom edge is worse than a missing one: it hands a reader
an unrelated file AS evidence.

Edges supply candidates and annotations. They never rank — that is hard rule
#3, decided by experiment.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from ._attrs import attribute_files
from ._calls import called_files
from ._imports import imports_of
from ._reexports import reexport_map

__all__ = ["ModuleIndex", "module_index", "python_edges"]

Edge = tuple[str, str]                    # (destination relpath, "import" | "call")


@dataclass(frozen=True, slots=True)
class ModuleIndex:
    """The repo's dotted module names, resolved to files, plus parsed trees.

    Built once per pass and shared by every file: resolution is a repo-wide
    question, and parsing each file once here is what keeps the pass one
    traversal instead of one per importer.
    """

    by_module: dict[str, str]                 # "pkg.mod" -> relpath
    by_symbol: dict[str, str]                 # "pkg.mod.Name" -> relpath
    trees: dict[str, ast.Module]
    by_attribute: dict[str, str]              # "audio_processor" -> relpath
    reexports: dict[str, str]                 # "pkg.Name" -> defining relpath


def module_index(sources: dict[str, str]) -> ModuleIndex:
    """Index every parseable Python file by the name it is imported AS.

    Filled locally and constructed at the end, so no half-built index is ever
    reachable — resolution against one is silently wrong, not loud. The two
    derived maps are LATER passes, in order: re-exports need the modules
    resolved, and attributes need the re-exports."""
    by_module: dict[str, str] = {}
    by_symbol: dict[str, str] = {}
    trees: dict[str, ast.Module] = {}
    for relpath, source in sources.items():
        if not relpath.endswith(".py"):
            continue
        module = dotted(relpath)
        by_module[module] = relpath
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue          # a broken file in a working tree is normal
        trees[relpath] = tree
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                by_symbol[f"{module}.{node.name}"] = relpath
    bare = ModuleIndex(by_module, by_symbol, trees, {}, {})
    forwarded = reexport_map(bare)
    resolved = ModuleIndex(by_module, by_symbol, trees, {}, forwarded)
    return ModuleIndex(by_module, by_symbol, trees,
                       attribute_files(resolved), forwarded)


def dotted(relpath: str) -> str:
    """`src/pkg/mod.py` -> `pkg.mod`, `pkg/__init__.py` -> `pkg`.

    `src/` is a packaging convention, not part of the module path, and a
    package is imported by its directory name rather than its `__init__`.
    """
    module = relpath.removesuffix(".py").replace("/", ".").removeprefix("src.")
    return module.removesuffix(".__init__")


def python_edges(relpath: str, index: ModuleIndex) -> list[Edge] | None:
    """This file's edges, or None when it could not be parsed.

    None rather than `[]`: "not examined" and "examined, nothing found" are
    different facts, and only the second should replace what is stored.
    Sorted, because two runs over the same source must write the same rows.
    """
    tree = index.trees.get(relpath)
    if tree is None:
        return None
    imports, aliases = imports_of(relpath, tree, index)
    calls = {(dst, "call")
             for dst in called_files(tree, aliases, index.by_attribute)}
    return sorted({(dst, kind) for dst, kind in imports | calls if dst != relpath})
