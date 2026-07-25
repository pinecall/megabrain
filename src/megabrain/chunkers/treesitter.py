"""Every non-Python language, through one walk.

The chunking engine already owns the hard part — cover, split, merge, breadcrumb,
partition — so a grammar contributes exactly what `units.ParseFn` asks for:
units to cut at, symbols to name, a skeleton to embed. The walk below is the
same for TypeScript and Rust; only the `LangSpec` table differs.

A parse failure is REPORTED, never raised. A file the grammar cannot read is
exactly the kind nobody can find by hand either, so it stays in the index as
line windows rather than disappearing twice over.
"""

from __future__ import annotations

from typing import Any

from ._langspec import LangSpec
from ._tsnodes import name_of, unwrap
from ._tssymbols import skeleton_of, symbols_of
from .units import Parsed, Unit

__all__ = ["parse_with", "parser_for"]

_PARSERS: dict[tuple[str, str], Any] = {}


def parser_for(spec: LangSpec, ext: str) -> Any:
    """One parser per (language, extension), built once.

    Cached because constructing it loads and links a grammar, which is slow
    enough to dominate a repository of small files.
    """
    key = (spec.name, ext)
    if key not in _PARSERS:
        from tree_sitter import Language, Parser

        _PARSERS[key] = Parser(Language(spec.grammar(ext)))
    return _PARSERS[key]


def parse_with(spec: LangSpec, relpath: str, source: str) -> Parsed:
    if not source.strip():
        return Parsed(units=(), symbols=(), skeleton="", ok=True)
    try:
        parser = parser_for(spec, relpath.rsplit(".", 1)[-1].lower())
        tree = parser.parse(source.encode())
    except Exception:              # noqa: BLE001 — a missing grammar is not a crash
        return Parsed(units=(), symbols=(), skeleton="", ok=False)
    raw = source.encode()
    symbols = tuple(symbols_of(spec, relpath, tree.root_node, raw))
    return Parsed(units=tuple(_units(spec, tree.root_node)), symbols=symbols,
                  skeleton=skeleton_of(relpath, symbols), ok=not tree.root_node.has_error)


def _units(spec: LangSpec, node: Any) -> list[Unit]:
    """Top-level declarations, with their members as cut points.

    Only declarations: a chunk that starts halfway through a function body is
    not a unit of meaning, it is a fragment that happens to parse.
    """
    found: list[Unit] = []
    for child in node.named_children:
        declared = unwrap(spec, child)
        if declared.type in spec.def_types:
            found.append(_unit(spec, declared))
    return found


def _unit(spec: LangSpec, node: Any) -> Unit:
    body = node.child_by_field_name(spec.body_field)
    children: tuple[Unit, ...] = ()
    if body is not None and node.type in spec.container_types:
        children = tuple(_unit(spec, unwrap(spec, inner))
                         for inner in body.named_children
                         if unwrap(spec, inner).type in spec.def_types)
    return Unit(start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                kind=spec.def_types[node.type],
                name=name_of(spec, node), children=children)


