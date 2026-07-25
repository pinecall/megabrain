"""Reading the SHAPES a caller sends, as opposed to its scalars.

Split from `arguments` by what the reader has to know: those functions turn one
value into one value, these have to decide what a whole request meant when the
caller packaged it a way the schema did not name. Every rule here is a habit
observed in the field, not a defensive reflex.
"""

from __future__ import annotations

import json
from typing import Any

from ._missing import Missing

__all__ = ["optional", "request", "operations"]

_REQUEST = ("task", "query", "question")
_OPERATIONS = ("operations", "edits", "ops")


def optional(arguments: dict[str, Any], name: str) -> str:
    """A string argument the caller may leave out entirely."""
    value = arguments.get(name)
    return value.strip() if isinstance(value, str) else ""


def request(arguments: dict[str, Any]) -> str:
    """What was asked, under whichever key the caller used.

    `task` wins when both arrive: a caller that filled both meant to change
    something and described it twice, and answering the question is the reading
    that leaves them without an edit surface. `question` stays accepted because
    it is what this argument was called before.
    """
    for name in _REQUEST:
        if found := optional(arguments, name):
            return found
    raise Missing("send `task` for a change you are about to make, or `query` "
                  "for a how/where/why question — one of them, as a non-empty "
                  "string")


def operations(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    """The edit batch, however the caller packaged it.

    FIELD RUN: an agent sent `{edits: "<json string>"}` — a habit from tools
    whose arguments are stringly typed — and it failed as a missing list. The
    alias and the encoded form are both accepted, because the alternative is a
    caller who cannot tell a wrong key from a wrong repository.
    """
    for name in _OPERATIONS:
        found = arguments.get(name)
        if isinstance(found, str) and found.strip():
            try:
                found = json.loads(found)
            except ValueError as bad:
                raise Missing(f"`{name}` is a string that is not JSON: {bad}") from bad
        if isinstance(found, dict):
            found = [found]                  # a single op, unwrapped
        if isinstance(found, list) and found:
            return [op for op in found if isinstance(op, dict)]
    raise Missing("`operations` is required — a non-empty list of "
                  "{file, find, replace, count?}")
