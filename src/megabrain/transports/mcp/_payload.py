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

__all__ = ["optional", "first_of", "operations"]

_OPERATIONS = ("operations", "edits", "ops")


def optional(arguments: dict[str, Any], name: str) -> str:
    """A string argument the caller may leave out entirely."""
    value = arguments.get(name)
    return value.strip() if isinstance(value, str) else ""


def first_of(arguments: dict[str, Any], *names: str) -> str:
    """The first of `names` the caller actually filled.

    Each tool has ONE canonical field; the rest are the spellings a model
    reaches for anyway — `question` because that is what ask took before, and
    each tool accepting the other's word because a model that picked the right
    tool and the wrong noun has still said what it wants.
    """
    for name in names:
        if found := optional(arguments, name):
            return found
    raise Missing(f"`{names[0]}` is required, as a non-empty string")


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
