"""Declarations the grammar refuses to call declarations: `it('…', fn)`.

A mocha or jest file declares its units by CALLING a function with a label and a
closure. To tree-sitter that is an expression statement, so a test file parses
perfectly and yields no symbol — express's `test/res.attachment.js` came back
with two, both of them `require` bindings, while the fifteen cases a reader
actually edits were unnameable and therefore unreachable: `_mentions` resolves a
match to the symbol CONTAINING it, and inside those files nothing contains
anything.

Groups are recursed into but never recorded, and that asymmetry is the whole
design. A `describe` spans the file, and `_idents.outermost` keeps the symbol no
other symbol contains — so recording the group makes it swallow every case
inside it and hand back one row meaning "this file", which is the row the reader
already had.
"""

from __future__ import annotations

from typing import Any

from ._langspec import LangSpec
from ._tsnodes import FUNCTION_VALUES

__all__ = ["called_block", "MAX_LABEL"]

MAX_LABEL = 60
"""Characters of a test's label kept in its symbol name.

A case is named in prose — "should set Content-Disposition to attachment" — and
the whole sentence is the row; enough of it to recognise is not the whole
paragraph some suites write."""

_STRINGS = ("string", "template_string")


def called_block(spec: LangSpec, node: Any) -> tuple[str, str, Any] | None:
    """`(name, kind, body_to_recurse)` for a call that declares, else None.

    `kind` empty means a GROUP: recurse, record nothing. A non-None body is
    returned only for groups, so a case's closure is never walked — a helper
    defined inside one `it` is not a second place to go.
    """
    call = _call(node)
    if call is None:
        return None
    function = call.child_by_field_name("function")
    arguments = call.child_by_field_name("arguments")
    if function is None or arguments is None:
        return None
    # `describe.only(…)` and `it.each([…])(…)` are the same declaration wearing a
    # modifier, and a suite uses them exactly where the plain form would be.
    base = function.text.decode().split(".")[0]
    children = list(arguments.named_children)
    if not children or children[-1].type not in FUNCTION_VALUES:
        return None
    if base in spec.group_calls:
        block = children[-1].child_by_field_name("body")
        return (base, "", block) if block is not None else None
    if base in spec.case_calls:
        return f"{base} {_label(children)}".strip(), "test", None
    return None


def _call(node: Any) -> Any | None:
    """The call inside a statement, if the statement is just a call."""
    inner = node
    if inner.type == "expression_statement" and inner.named_child_count:
        inner = inner.named_children[0]
    return inner if inner.type == "call_expression" else None


def _label(children: list[Any]) -> str:
    """The case's own words, or nothing.

    Nothing is the right answer for `beforeEach(fn)`: a hook carries no label and
    is still an edit site, so it is named by the call alone rather than skipped.
    """
    if children[0].type not in _STRINGS:
        return ""
    text = children[0].text.decode(errors="replace").strip("'\"`")
    return text if len(text) <= MAX_LABEL else text[:MAX_LABEL - 1] + "…"
