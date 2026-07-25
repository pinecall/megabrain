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

__all__ = ["EditOp", "EditRow", "EditResult", "NEW_CODE"]

NEW_CODE = "<<<WRITE THE NEW CODE HERE>>>"
"""The hole a prepared batch leaves for the CALLER's own code.

MEASURED, and it is why the engine stopped writing code at all. Asked to guard
the `write` tool against non-regular files, `megabrain_code` found both files
and both insertion points in a 1 220-file repository — and then authored a
guard that ran AFTER the write it was guarding, inside an unclosed `try:` that
does not compile. The agent spent four retrieval calls and two reads undoing
it, and finished slower than the arm that had no megabrain at all.

The split that came out of it: the engine supplies what it can be exactly
right about — which file, which line, the anchor text verbatim from the index —
and the caller supplies the one thing it alone knows, the change. The caller
also runs the tests, so the code and its verification stay with the same party.

Declared in the contract because two layers must agree on it: `ask` writes the
hole and `edits` REFUSES any operation that still contains it. A batch applied
with the placeholder intact would write this string into the source.
"""


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
