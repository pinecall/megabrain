"""Finding the declared NAME of a node, across grammars that all hide it
somewhere different.

Three places, in order: a field on the node, one of the language's fallback
fields, or a field on a child one level down. Every one of those was added for a
language that would otherwise contribute anonymous chunks — and an anonymous
chunk cannot be cited, searched by name, or put in an outline.
"""

from __future__ import annotations

from typing import Any

from ._langspec import LangSpec

__all__ = ["name_of"]


def name_of(spec: LangSpec, node: Any) -> str | None:
    """The declared name, through whichever field this grammar puts it in."""
    for field in (spec.name_field, *spec.extra_name_fields):
        found = node.child_by_field_name(field)
        if found is not None:
            return str(found.text.decode())
    return _nested_name(spec, node)


def _nested_name(spec: LangSpec, node: Any) -> str | None:
    """Names that live one level down — Go's `const_spec`, PHP's `const_element`.

    The name is either a FIELD of that child or, when the grammar declares no
    such field, a child whose TYPE is the field's name. Both shapes appear in
    grammars that otherwise look identical.
    """
    via = spec.name_via.get(node.type)
    if via is None:
        return None
    child_type, field = via
    for child in node.named_children:
        if child.type != child_type:
            continue
        found = child.child_by_field_name(field) or next(
            (inner for inner in child.named_children if inner.type == field), None)
        if found is not None:
            return str(found.text.decode())
    return None
