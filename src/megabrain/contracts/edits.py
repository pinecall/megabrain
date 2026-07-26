"""The write half of the loop: what an edit asks for, and what it reports.

Declared beside the read contracts because it is the same kind of promise — a
shape four surfaces (CLI, MCP, HTTP, the studio) agree on rather than
rediscover from the producer.

`ok=False` is not an exception. A failed batch is a NORMAL, expected result the
caller reads and retries from: which op failed, and why, in enough detail to
fix the string without re-reading the file.
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["EditOp", "EditRow", "EditResult"]


class _EditRequired(TypedDict):
    file: str
    find: str
    replace: str


class EditOp(_EditRequired, total=False):
    """One exact-string replacement.

    `find` and `replace` are the CALLER's own strings, applied verbatim. The
    engine never invents content — the same stance the narrator's splicing
    takes, on the write side.
    """

    count: int
    """How many occurrences `find` must match, default 1.

    A REQUIREMENT, not a limit: an op whose text appears twice fails rather
    than editing the first, because "the first one" is not something the
    caller asked for and not something they can see."""


class _RowRequired(TypedDict):
    op: int
    file: str


class EditRow(_RowRequired, total=False):
    """What became of one op. Exactly one of `replaced` or `error` is set."""

    replaced: int
    error: str


class EditResult(TypedDict):
    """The batch's verdict. `written` is empty whenever `ok` is False —
    transactional means nothing reached disk, not that some did."""

    ok: bool
    report: list[EditRow]
    written: list[str]
