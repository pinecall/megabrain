"""Reading one tree-sitter node: its name, its declaration line, its wrapper.

The three questions the walk asks of every node, kept apart from the walk
itself because each is a pile of grammar-specific special cases and the walk is
four lines of recursion.
"""

from __future__ import annotations

from typing import Any

from ._langspec import LangSpec

__all__ = ["name_of", "unwrap", "signature_of", "assigned_method"]

MAX_SIGNATURE = 140

_FUNCTION_VALUES = ("function", "function_expression", "generator_function",
                    "arrow_function")


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


def unwrap(spec: LangSpec, node: Any) -> Any:
    """`export class Foo` -> the class.

    Nearly every declaration in a modern TypeScript file is exported, so a walk
    that stops at the wrapper finds a file with no declarations at all — which
    is indistinguishable from having no chunker for the language.
    """
    if not spec.unwrap_exports or node.type != "export_statement":
        return node
    declared = node.child_by_field_name("declaration")
    if declared is not None:
        return declared
    return next((child for child in node.named_children
                 if child.type in spec.def_types), node)


def signature_of(node: Any, source: bytes) -> str:
    """The first line of the declaration, without its body."""
    head = source[node.start_byte:node.end_byte].split(b"\n", 1)[0]
    line = head.decode(errors="replace").strip().rstrip("{").strip()
    return line if len(line) <= MAX_SIGNATURE else line[:MAX_SIGNATURE - 1] + "…"


def assigned_method(spec: LangSpec, node: Any) -> tuple[str, str] | None:
    """`Route.prototype.dispatch = function () {}` -> ("Route.prototype.dispatch",
    "method"), or None.

    How a large part of npm declares its API. Without it those files hold no
    nameable symbol, so nothing in them can be cited or searched by name — and
    Express's entire router is written this way.
    """
    if not spec.assign_defs:
        return None
    inner = node
    if inner.type == "expression_statement" and inner.named_child_count:
        inner = inner.named_children[0]
    if inner.type != "assignment_expression":
        return None
    left = inner.child_by_field_name("left")
    right = inner.child_by_field_name("right")
    if left is None or right is None:
        return None
    if left.type not in ("member_expression", "subscript_expression"):
        return None
    if right.type not in _FUNCTION_VALUES:
        return None
    return str(left.text.decode()), "method"
