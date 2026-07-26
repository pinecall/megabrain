"""Reading one tree-sitter node: its name, its declaration line, its wrapper.

The three questions the walk asks of every node, kept apart from the walk
itself because each is a pile of grammar-specific special cases and the walk is
four lines of recursion.
"""

from __future__ import annotations

from typing import Any

from ._langspec import LangSpec
from ._tsnames import name_of

__all__ = ["name_of", "unwrap", "signature_of", "assigned_method",
           "FUNCTION_VALUES"]

MAX_SIGNATURE = 140

FUNCTION_VALUES = ("function", "function_expression", "generator_function",
                   "arrow_function")
"""Node types whose value IS a function.

Shared with `_tscalls`, which asks the same question of a call's last argument:
both are looking for the place a function literal is being handed to something."""


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


def signature_of(node: Any, source: bytes, body_field: str = "body") -> str:
    """The declaration, cut where its BODY begins.

    Bounded by the body NODE rather than by the first `{`: a C++ one-liner puts
    the whole body on the declaration line (`int charge() const { return
    total_; }`) and a text cut leaks it into the file-level vector, while
    cutting at the first brace instead mangles `function Card({ title }: ...)`
    — TypeScript writes braces in its parameters. The grammar already knows
    where the body starts; nothing else does.
    """
    body = node.child_by_field_name(body_field)
    end = body.start_byte if body is not None else node.end_byte
    head = source[node.start_byte:max(node.start_byte, end)].split(b"\n", 1)[0]
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
    if right.type not in FUNCTION_VALUES:
        return None
    return str(left.text.decode()), "method"
