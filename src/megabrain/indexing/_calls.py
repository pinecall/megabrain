"""Which calls in a file reach another file.

The alias map decides: a call is an edge only when its receiver is a name some
import bound to a file. That is the extractor's whole rule, and this module is
the half that applies it.
"""

from __future__ import annotations

import ast

__all__ = ["called_files"]


def called_files(tree: ast.Module, aliases: dict[str, str]) -> set[str]:
    """Files reached by a call written through an imported name."""
    return {file for node in ast.walk(tree) if isinstance(node, ast.Call)
            if (file := _resolve(node.func, aliases)) is not None}


def _resolve(func: ast.expr, aliases: dict[str, str]) -> str | None:
    """`run()`, `mod.run()`, `a.b.run()`, `Cls(...).run()` -> the file, or None.

    The receiver is matched LONGEST FIRST: with both `a` and `a.b` imported,
    `a.b.run()` belongs to `a.b`.
    """
    if isinstance(func, ast.Name):
        return aliases.get(func.id)
    if not isinstance(func, ast.Attribute):
        return None
    parts = _receiver(func)
    for cut in range(len(parts), 0, -1):
        if (file := aliases.get(".".join(parts[:cut]))) is not None:
            return file
    return None


def _receiver(func: ast.Attribute) -> list[str]:
    """The dotted receiver of an attribute call: `a.b.f()` -> ['a', 'b'],
    `Cls(...).f()` -> ['Cls'], `f().g()` -> []."""
    parts: list[str] = []
    node: ast.expr = func.value
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Call):
        node = node.func           # `Cls(...).f()` — the class is the receiver
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif parts:
        return []                  # an unresolvable base makes the chain useless
    return parts[::-1]
