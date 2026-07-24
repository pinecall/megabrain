"""Resolving what a file imports: the edges, and the names they bound.

The alias map this produces is the join with `_calls`: an import records where
a name CAME from, and only a call through such a name is an edge.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .edges import Edge, ModuleIndex

__all__ = ["imports_of"]


def imports_of(relpath: str, tree: ast.Module,
               index: "ModuleIndex") -> tuple[set["Edge"], dict[str, str]]:
    """Import edges, and the local names they bound to a file."""
    own = _dotted_parts(relpath)
    edges: set[Edge] = set()
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            _from_import(node, own, index, edges, aliases)
        elif isinstance(node, ast.Import):
            _plain_import(node, index, edges, aliases)
    return edges, aliases


def _from_import(node: ast.ImportFrom, own: list[str], index: "ModuleIndex",
                 edges: set["Edge"], aliases: dict[str, str]) -> None:
    """`from X import a, b` — and each imported name may itself be a module."""
    target = _target(node, own)
    module_file = index.by_module.get(target)
    if module_file:
        edges.add((module_file, "import"))
    for alias in node.names:
        # `from pkg import util` binds the SUBMODULE when one exists: a later
        # `util.helper()` belongs to util.py, not to the package's __init__.
        submodule = index.by_module.get(f"{target}.{alias.name}" if target else alias.name)
        if submodule:
            edges.add((submodule, "import"))
            aliases[alias.asname or alias.name] = submodule
        elif module_file:
            # A re-exported symbol may live in a different file than the module
            # that exposes it; the module is the fallback, not the answer.
            aliases[alias.asname or alias.name] = index.by_symbol.get(
                f"{target}.{alias.name}", module_file)


def _plain_import(node: ast.Import, index: "ModuleIndex",
                  edges: set["Edge"], aliases: dict[str, str]) -> None:
    """`import a.b [as ab]` — the alias is what a call can be written through."""
    for alias in node.names:
        file = index.by_module.get(alias.name)
        if file:
            edges.add((file, "import"))
            # Without `as`, `import a.b` binds `a` but is USED as `a.b`, so the
            # dotted path is the name a call site actually spells.
            aliases[alias.asname or alias.name] = file


def _target(node: ast.ImportFrom, own: list[str]) -> str:
    """The absolute module a `from ... import` names.

    A relative import counts levels UP from the importing module's own package,
    which is why the importer's dotted path has to be known here.
    """
    if not node.level:
        return node.module or ""
    base = own[:len(own) - node.level + 1] if node.level > 1 else own
    return ".".join([*base, *(node.module.split(".") if node.module else [])])


def _dotted_parts(relpath: str) -> list[str]:
    """The importing module's package path: `pkg/sub/svc.py` -> ['pkg', 'sub'].

    `__init__.py` is NOT stripped here — a package's own `__init__` sits one
    level shallower, and dropping it would make every relative import inside it
    climb one package too far.
    """
    module = relpath.removesuffix(".py").replace("/", ".").removeprefix("src.")
    return module.split(".")[:-1]
