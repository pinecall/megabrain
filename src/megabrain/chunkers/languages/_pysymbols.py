"""What a Python file NAMES — the symbol table behind outlines, the lexical
lane and go-to-definition.

Separate from unit extraction on purpose: units answer "where may this file be
cut", symbols answer "what does this file declare". The two often coincide, but
a module constant is a symbol and never a cut point, and a merged block is a
chunk that declares several things.
"""

from __future__ import annotations

import ast

from .._cast._signature import signature_of
from ..model import Symbol

__all__ = ["symbols_of"]

Def = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
_Scoped = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


def symbols_of(relpath: str, node: ast.AST, prefix: str = "") -> list[Symbol]:
    """Every definition and module constant, qualified by its container.

    `handle` alone is ambiguous in any repo with more than one service, so a
    method is recorded as `Service.handle`. Constants are collected at module
    level only: a local named in caps is not configuration.
    """
    out: list[Symbol] = []
    for child in _body(node):
        if isinstance(child, Def):
            out.append(_definition(relpath, child, prefix, nested=bool(prefix)))
            out.extend(symbols_of(relpath, child, f"{prefix}{child.name}."))
        elif isinstance(child, ast.Assign | ast.AnnAssign) and not prefix:
            out.extend(_constants(relpath, child))
    return out


def _body(node: ast.AST) -> list[ast.stmt]:
    """The statements inside a node, for the node types that have them.

    Matched rather than reached for with `getattr`: `IfExp.body` is an
    expression, and a caller iterating it would get something that is not a
    statement at all.
    """
    return node.body if isinstance(node, _Scoped) else []


def _definition(relpath: str, node: Def, prefix: str, *, nested: bool) -> Symbol:
    return Symbol(file=relpath, name=f"{prefix}{node.name}", kind=kind_of(node, nested=nested),
                  line=first_line(node), end_line=node.end_lineno or node.lineno,
                  signature=signature_of(node),
                  decorators=tuple(ast.unparse(d) for d in node.decorator_list),
                  doc=(ast.get_docstring(node) or "").split("\n")[0] or None)


def _constants(relpath: str, node: ast.Assign | ast.AnnAssign) -> list[Symbol]:
    """Module-level assignments — the untyped AND the annotated form.

    Configuration lives in constants, and a search for a setting has to reach
    the line that defines it. `MAX: int = 10` is the same declaration as
    `MAX = 10` with better manners — `X: Final = ...` is the house style of
    the reference SDK itself — so skipping AnnAssign silently dropped every
    typed constant from the lexical lane and the outlines.
    """
    if isinstance(node, ast.AnnAssign):
        if not isinstance(node.target, ast.Name):
            return []
        value = f" = {ast.unparse(node.value)[:60]}" if node.value is not None else ""
        return [Symbol(file=relpath, name=node.target.id, kind="constant",
                       line=node.lineno, end_line=node.end_lineno or node.lineno,
                       signature=f"{node.target.id}: {ast.unparse(node.annotation)}{value}")]
    return [Symbol(file=relpath, name=target.id, kind="constant", line=node.lineno,
                   end_line=node.end_lineno or node.lineno,
                   signature=f"{target.id} = {ast.unparse(node.value)[:60]}")
            for target in node.targets if isinstance(target, ast.Name)]


def first_line(node: Def) -> int:
    """Where a definition really starts: its DECORATORS.

    `@property` above a method belongs to that method; starting the unit after
    it would file the decorator with the previous chunk, where it means nothing.
    """
    return min([node.lineno, *(d.lineno for d in node.decorator_list)])


def kind_of(node: ast.AST, *, nested: bool = False) -> str:
    if isinstance(node, ast.ClassDef):
        return "class"
    prefix = "async_" if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{'method' if nested else 'function'}"
