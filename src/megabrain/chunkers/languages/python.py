"""Python, via the stdlib `ast`.

No grammar to install and no version drift: the interpreter running the engine
is the one that defines the language, so a syntax feature works the day the
runtime supports it.
"""

from __future__ import annotations

import ast

from .._cast._signature import skeleton_of
from ..units import Parsed, Unit
from ._pysymbols import first_line, kind_of, symbols_of

__all__ = ["parse"]

Def = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def parse(relpath: str, source: str) -> Parsed:
    """Top-level definitions as units, everything nameable as a symbol.

    A `SyntaxError` is REPORTED, never raised: the engine falls back to line
    windows and the file stays in the index. A file the parser cannot read is
    exactly the kind nobody can find by hand either, so dropping it would
    remove it from reach twice over.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return Parsed(units=(), symbols=(), skeleton="", ok=False)
    symbols = tuple(symbols_of(relpath, tree))
    return Parsed(units=tuple(_units(tree)), symbols=symbols,
                  skeleton=skeleton_of(symbols), ok=True)


def _units(tree: ast.Module) -> list[Unit]:
    """One unit per top-level definition, with its members as cut points.

    Only top-level: nesting deeper would offer the engine cut points inside a
    method, and a chunk that starts halfway through a function body is not a
    unit of meaning — it is a fragment that happens to parse.
    """
    return [_unit(node) for node in tree.body if isinstance(node, Def)]


def _unit(node: Def) -> Unit:
    """A definition and the members it can be split at, if it grows too large."""
    children = tuple(_unit(inner) for inner in node.body if isinstance(inner, Def))
    return Unit(start_line=first_line(node), end_line=node.end_lineno or node.lineno,
                kind=kind_of(node), name=node.name, children=children)
