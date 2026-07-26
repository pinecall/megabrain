"""Shortening a quote from the MIDDLE, so its head and its tail both survive.

MEASURED, and reported independently by both agents of the same round. Told to
insert a sibling block AFTER a 157-line `describe`, the render cut the quote at
40 lines — so the closing `end`, the one line the instruction depended on, was
absent from the answer. One agent inverted the operation to anchor on the
block's opening instead; the other, editing inside a `try:`, never saw the
`except` clause and reasoned around a handler it could not read.

Their proposal, adopted verbatim because it is strictly cheaper than what they
were given: keep the first lines, say how many were dropped, keep the last
ones. Cutting from the tail spends the whole budget on a block's opening, and
an opening is the part a reader can already infer.
"""

from __future__ import annotations

__all__ = ["elide", "MAX_QUOTE_LINES", "TAIL_LINES"]

MAX_QUOTE_LINES = 40
"""Lines any single citation may print, head and tail together.

Enforced because asking did not work. Told to cite "one test, or one method —
not the class or describe that contains it", the model cited a 117-line
`describe` holding fifteen tests: 3 518 characters, 55% of the whole answer, to
show what one of them looks like. Forty lines is two or three complete
examples, which is what imitating a style actually needs."""

TAIL_LINES = 12
"""Lines kept from the END of an elided quote.

Enough for a closing `end` with the last case above it, or an `except` clause
with its handler — the block's exits. The head keeps the rest, because a
declaration's opening is what says what the block IS."""


def elide(lines: list[str], first_line: int) -> tuple[list[str], str]:
    """`lines` shortened to the cap, plus a note for the caller's header.

    Returns the lines to PRINT — with the marker already in place — so callers
    cannot render the gap silently. `first_line` is the file line `lines[0]`
    sits on, which is what lets the marker name real line numbers instead of
    offsets into a quote nobody can see.
    """
    if len(lines) <= MAX_QUOTE_LINES:
        return lines, ""
    head = MAX_QUOTE_LINES - TAIL_LINES
    dropped = len(lines) - MAX_QUOTE_LINES
    gap_start = first_line + head
    marker = (f"… ‹elided {dropped} lines: "
              f"L{gap_start}-{gap_start + dropped - 1}› …")
    return [*lines[:head], marker, *lines[-TAIL_LINES:]], f" ({dropped} lines elided)"
