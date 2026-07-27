"""Where a Python file uses a name, and what its imported names denote.

One AST walk, two products. `sites` is name -> [(line, receiver)] for every
call and every import site; `aliases` is alias -> (relative level, dotted path)
for every name an import bound.

The receiver is the part that earns its keep. `None` is reserved for a PLAIN
call or an import site — evidence that resolves by itself. An attribute call
records the base name so it can be checked against the aliases, and `"?"` when
the base cannot be named at all: `os.environ.get()` once passed as a plain call
and was ranked as verified evidence of a connection it had nothing to do with.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

__all__ = ["Uses", "py_uses"]

Site = tuple[int, str | None]


@dataclass(frozen=True, slots=True)
class Uses:
    aliases: dict[str, tuple[int, str]]
    sites: dict[str, list[Site]]


def py_uses(source: str) -> Uses | None:
    """None when the file does not parse — the caller falls back lexically."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    aliases: dict[str, tuple[int, str]] = {}
    calls: dict[str, list[Site]] = {}
    imports: dict[str, list[Site]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            _record_call(node, calls)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = (0, alias.name)
        elif isinstance(node, ast.ImportFrom):
            _record_from(node, aliases, imports)
    sites = {name: sorted(calls.get(name, []), key=lambda site: site[0])
             + sorted(imports.get(name, []), key=lambda site: site[0])
             for name in {*calls, *imports}}
    return Uses(aliases=aliases, sites=sites)


def _record_call(node: ast.Call, calls: dict[str, list[Site]]) -> None:
    func = node.func
    if isinstance(func, ast.Name):
        calls.setdefault(func.id, []).append((node.lineno, None))
    elif isinstance(func, ast.Attribute):
        calls.setdefault(func.attr, []).append((node.lineno, _base(func.value)))


def _base(value: ast.expr) -> str:
    """The name at the bottom of an `a.b.c()` chain, or "?" when unnameable."""
    while isinstance(value, ast.Attribute):
        value = value.value
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        return value.func.id           # `Cls(...).f()` — the class is the base
    return "?"


def _record_from(node: ast.ImportFrom, aliases: dict[str, tuple[int, str]],
                 imports: dict[str, list[Site]]) -> None:
    module = node.module or ""
    for alias in node.names:
        imports.setdefault(alias.name, []).append((node.lineno, None))
        dotted = f"{module}.{alias.name}" if module else alias.name
        aliases[alias.asname or alias.name] = (node.level, dotted)
