"""What a package's `__init__.py` forwards, and where it really comes from.

MEASURED across nine repositories. `from ..storage import PIN_KIND` files its
edge against `storage/__init__.py`, because that is the module the statement
names — while PIN_KIND is defined in `storage/_graph.py`, which the __init__
re-exports. The real dependency exists in TWO hops and the graph held only the
first, so a walkthrough that moved from the consumer to the defining file looked
unsupported. Python packages are built this way, so the gap hit every
well-formed one.

Only what an `__init__.py` ACTUALLY forwards, read from its own import
statements. Guessing which module a name might live in is the phantom edge this
extractor exists to refuse.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .edges import ModuleIndex

__all__ = ["reexport_map"]


def reexport_map(index: "ModuleIndex") -> dict[str, str]:
    """`"pkg.Name"` -> the file the package's __init__ imported Name FROM.

    Keyed by the name a CONSUMER writes, so `from ._impl import Thing as T` is
    reachable as `pkg.T` — the alias is what the outside world sees.
    """
    out: dict[str, str] = {}
    for relpath, tree in index.trees.items():
        if not relpath.endswith("__init__.py"):
            continue
        package = _package_of(relpath)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                _forwarded(node, package, relpath, index, out)
    return out


def _forwarded(node: ast.ImportFrom, package: str, relpath: str,
               index: "ModuleIndex", out: dict[str, str]) -> None:
    """One `from X import a, b` inside a package's __init__."""
    source = _source_module(node, package)
    origin = index.by_module.get(source)
    if origin is None or origin == relpath:
        return
    for alias in node.names:
        if alias.name != "*":       # a star import forwards names nothing lists
            out[f"{package}.{alias.asname or alias.name}"] = origin


def _source_module(node: ast.ImportFrom, package: str) -> str:
    """The absolute module an __init__'s import points at.

    A relative import inside `pkg/__init__.py` counts levels from `pkg` itself,
    not from its parent — the __init__ IS the package, which is the one place
    where `_dotted_parts` in `_imports` would climb one level too far.
    """
    if not node.level:
        return node.module or ""
    base = package.split(".")[:len(package.split(".")) - node.level + 1]
    return ".".join([*base, *(node.module.split(".") if node.module else [])])


def _package_of(relpath: str) -> str:
    """`src/pkg/sub/__init__.py` -> `pkg.sub`."""
    module = relpath.removesuffix(".py").replace("/", ".").removeprefix("src.")
    return module.removesuffix(".__init__")
