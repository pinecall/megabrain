"""Lightweight local typing: which variables hold what.

`store.commit()` is unlinkable on its own — the receiver is a variable, and
nothing in the index says what a variable is. But `store = Store(...)` and
`with Store(...) as store` say it plainly, and those two forms cover most of
how objects enter a function in practice. That is the whole ambition here: no
inference engine, just the two statements that are already an answer.
"""

from __future__ import annotations

import ast

__all__ = ["constructors"]


def constructors(tree: ast.Module) -> dict[str, str]:
    """variable -> the name it was constructed from."""
    traced: dict[str, str] = {}
    for node in ast.walk(tree):
        value, names = _binding(node)
        if value is not None and names and isinstance(value, ast.Call) \
                and isinstance(value.func, ast.Name):
            for name in names:
                traced[name] = value.func.id
    return traced


def _binding(node: ast.AST) -> tuple[ast.expr | None, list[str]]:
    if isinstance(node, ast.Assign):
        return node.value, [t.id for t in node.targets if isinstance(t, ast.Name)]
    if isinstance(node, ast.withitem):
        bound = node.optional_vars
        return node.context_expr, [bound.id] if isinstance(bound, ast.Name) else []
    return None, []
