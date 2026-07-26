"""The citation grammar: how the model points at code it may not write.

Every spelling accepted here came from a real transcript, and each one was
added because the alternative is worse than ugly: an unmatched citation leaks
into the answer as raw `[[k:line]]` litter exactly where the evidence should
be. One run cited almost entirely in point form and rendered a walkthrough with
no code in it at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Citation", "parse_citations", "CITATION", "PARTIAL"]

# `[Ll]?` and the loose spacing are not politeness: the chunk headers in the
# prompt read "L1-172", so models mirror that as [[0:L1-172]].
_RANGE = r"[Ll]?\d+(?:\s*-\s*[Ll]?\d+)?"

# One reference inside the brackets: `3`, `3:10-20`, `3:10-20, 30-40`.
_ONE = rf"(\d+)((?::\s*{_RANGE})(?:\s*,\s*{_RANGE})*)?"

# DOUBLE brackets, so the model can still write [1] in prose without collision.
#
# And the GROUPED form — `[[1:173-240], [2:241-307]]` — because models write it
# unprompted and rejecting it printed both citations as prose: the reader was
# given two file/line ranges and no code. Accepting it costs one alternation;
# refusing it cost a whole answer.
CITATION = re.compile(rf"\[\[\s*{_ONE}(?:\s*\]?\s*,\s*\[?\s*{_ONE})*\s*\]?\s*\]\]")
_INNER = re.compile(_ONE)

# A citation that is still ARRIVING, at the tail of a stream buffer. Held back
# rather than emitted: a half-written `[[3:70` printed as prose cannot be taken
# back once the reader has seen it.
#
# The rule is the grammar's own terminator: a citation ends ONLY at `]]`, so
# everything from the last `[[` with no `]]` after it is undecidable. Spelled
# that way — rather than as a list of valid prefixes — because the prefix list
# went stale the day the grammar grew the grouped form: `[[1:173-240], ` has a
# lone `]` inside it, the old pattern read that as "not a citation tail", and
# the exact reported failure came back one layer down, only when a delta
# boundary fell inside the group. Bounded to one line: a `[[` the model
# abandons mid-answer must flush at the newline, not jam the stream forever.
PARTIAL = re.compile(r"\[\[(?:[^\]\n]|\](?!\]))*$|\[$")


@dataclass(frozen=True, slots=True)
class Citation:
    """One reference. Empty `ranges` means the whole chunk."""

    index: int
    ranges: tuple[tuple[int, int], ...] = ()


def parse_citations(text: str) -> list[Citation]:
    """Every reference in the text, in order.

    One bracket pair can hold SEVERAL — the grouped form — so this is a flat
    list rather than one citation per match.
    """
    out: list[Citation] = []
    for match in CITATION.finditer(text):
        out.extend(_references(match.group(0)))
    return out


def _references(bracketed: str) -> list[Citation]:
    inner = bracketed.strip("[] \t")
    return [Citation(index=int(part.group(1)), ranges=_ranges(part.group(2)))
            for part in _INNER.finditer(inner)]


def _ranges(spec: str | None) -> tuple[tuple[int, int], ...]:
    """`:10-12, 14-20` -> ((10, 12), (14, 20)). A POINT becomes (n, n).

    A point is a real citation form — models write `[[4:772]]` unprompted —
    and the splice widens it to the enclosing symbol rather than pasting one
    naked line, which explains nothing.
    """
    if not spec:
        return ()
    out: list[tuple[int, int]] = []
    for part in spec.lstrip(":").split(","):
        bounds = [int(n.strip().lstrip("Ll")) for n in part.split("-") if n.strip()]
        if bounds:
            out.append((bounds[0], bounds[-1]))
    return tuple(out)
