"""What a tree-sitter file NAMES, and the skeleton built from it.

Separate from unit extraction for the same reason the Python chunker separates
them: units answer "where may this file be cut", symbols answer "what does this
file declare". They often coincide and they are not the same question — a
CommonJS `proto.use = function () {}` is a symbol and never a cut point.
"""

from __future__ import annotations

from typing import Any

from ..model import Symbol
from ._calls import called_block
from ._langspec import LangSpec
from ._nodes import assigned_method, name_of, signature_of, unwrap

__all__ = ["symbols_of", "skeleton_of"]


def symbols_of(spec: LangSpec, relpath: str, node: Any, raw: bytes,
             prefix: str = "") -> list[Symbol]:
    """Everything the file names, qualified by its container.

    `open` alone is ambiguous in any repo with more than one service, so a
    method is recorded as `SessionService.open`.
    """
    found: list[Symbol] = []
    for child in node.named_children:
        declared = unwrap(spec, child)
        name = name_of(spec, declared) if declared.type in spec.def_types else None
        if name:
            found.append(_symbol(relpath, declared, f"{prefix}{name}",
                                 spec.def_types[declared.type], raw,
                                 spec.body_field))
            body = declared.child_by_field_name(spec.body_field)
            if declared.type in spec.container_types and body is not None:
                found += symbols_of(spec, relpath, body, raw, f"{prefix}{name}.")
            continue
        assigned = assigned_method(spec, child)
        if assigned is not None:
            found.append(_symbol(relpath, child, f"{prefix}{assigned[0]}",
                                 assigned[1], raw, spec.body_field))
            continue
        found += _from_call(spec, relpath, child, raw, prefix)
    return found


def _from_call(spec: LangSpec, relpath: str, child: Any, raw: bytes,
               prefix: str) -> list[Symbol]:
    """A `describe`/`it` call as declarations — see `_tscalls.called_block`.

    A group contributes nothing itself and its body contributes everything,
    which is why this returns a list rather than a symbol.
    """
    called = called_block(spec, child)
    if called is None:
        return []
    name, kind, block = called
    if not kind:
        return symbols_of(spec, relpath, block, raw, prefix)
    return [_symbol(relpath, child, f"{prefix}{name}", kind, raw, spec.body_field)]


def _symbol(relpath: str, node: Any, name: str, kind: str, raw: bytes,
            body_field: str) -> Symbol:
    return Symbol(file=relpath, name=name, kind=kind,
                  line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                  signature=signature_of(node, raw, body_field))


def skeleton_of(relpath: str, symbols: tuple[Symbol, ...]) -> str:
    """Declarations only, indented by nesting — one vector per file.

    A body in here would just re-embed what the chunks already say and tell the
    file-level signal nothing new.
    """
    lines = [f"# {relpath}"]
    lines += [("    " if "." in symbol.name else "") + symbol.signature
              for symbol in symbols]
    return "\n".join(lines)
