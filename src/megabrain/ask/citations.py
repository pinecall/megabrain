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

# DOUBLE brackets, so the model can still write [1] in prose without collision.
CITATION = re.compile(rf"\[\[(\d+)((?::\s*{_RANGE})(?:\s*,\s*{_RANGE})*)?\s*\]\]")

# A citation that is still ARRIVING, at the tail of a stream buffer. Held back
# rather than emitted: a half-written `[[3:70` printed as prose cannot be taken
# back once the reader has seen it.
PARTIAL = re.compile(r"\[(?:\[(?:\d+[\dLl\s:,-]*\]?)?)?$")


@dataclass(frozen=True, slots=True)
class Citation:
    """One reference. Empty `ranges` means the whole chunk."""

    index: int
    ranges: tuple[tuple[int, int], ...] = ()


def parse_citations(text: str) -> list[Citation]:
    return [_build(match) for match in CITATION.finditer(text)]


def _build(match: "re.Match[str]") -> Citation:
    return Citation(index=int(match.group(1)), ranges=_ranges(match.group(2)))


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
