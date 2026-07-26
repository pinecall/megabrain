"""The exact text to copy as `find` — short, unique, and never elided.

MEASURED, and it is the contract the engine itself was breaking. Every render
tells the reader to copy the anchor verbatim because it came from the index —
and then a quote past the cap arrives with `… ‹elided 117 lines› …` through the
middle, so the one string they were told to copy is not copyable. The reader
hand-picked a tail slice and carried the uniqueness judgement themselves:

  "an elided quote silently breaks the tool's own contract and hands the
   uniqueness judgement back to me — the one step where a mistake costs a
   failed batch plus a Read to recover."

The wide quote stays: it is what makes the edit CORRECT — the signature above,
the `except` below, the closing `end`. This is what makes it APPLICABLE, and
only when the two differ, so a short anchor is never printed twice.
"""

from __future__ import annotations

import re

from ..storage import Store
from ._elide import MAX_QUOTE_LINES
from ._quote import lines_of

__all__ = ["anchor_blocks", "MAX_ANCHOR_LINES"]

MAX_ANCHOR_LINES = 12
"""Lines an anchor may grow to before it is emitted ambiguous.

Past this the text is not an address any more, and `replace` reports a
non-unique `find` far better than this module can guess at one."""

_ANCHORED = re.compile(
    r"\[\[([^\]:]+):(\d+)-(\d+)\]\]\s*\n\s*APPLY\s+(\w+)")


def anchor_blocks(store: Store, surface: str) -> str:
    """Copyable `find` text for each anchor whose quote had to be elided."""
    blocks = []
    for path, start, end, mode in _ANCHORED.findall(surface):
        slice_ = _unique_slice(store, path.strip(), int(start), int(end), mode)
        if slice_:
            blocks.append(f"**`{path.strip()}` — copy this as `find`**\n"
                          f"```\n{slice_}\n```")
    if not blocks:
        return ""
    return ("\n\n## The anchors, exact — the quotes above are context, these "
            "are the strings to match\n" + "\n".join(blocks))


def _unique_slice(store: Store, path: str, lo: int, hi: int,
                  mode: str) -> str | None:
    """The shortest slice at the seam that occurs exactly once in the file.

    Grown from the END for an `insert_after` and from the START otherwise: the
    seam is where the reader's code meets the file, and it is the end of the
    anchor that carries the closing `end` an insertion has to land past.

    Returns None when the whole quote already fits — the render is then the
    copyable string, and printing it again is the duplication the readers kept
    naming as wasted budget.
    """
    lines = lines_of(store, path)
    if not lines or hi > len(lines) or hi - lo + 1 <= MAX_QUOTE_LINES:
        return None
    whole = "\n".join(lines)
    span = lines[lo - 1:hi]
    for size in range(1, min(MAX_ANCHOR_LINES, len(span)) + 1):
        text = "\n".join(span[-size:] if mode == "insert_after" else span[:size])
        if whole.count(text) == 1:
            return text
    return None
