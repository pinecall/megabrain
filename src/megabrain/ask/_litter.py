"""Citation-shaped text no splicer resolved, removed at the very end.

MEASURED: served a body carrying real line numbers, the model cited it as
`[[1214-1215]]` — neither a chunk index nor a repo path, so both splicers passed
over it and the reader got literal brackets in the middle of a sentence.

`rescue` cannot reach this: it APPENDS a repaired fragment rather than editing
prose the splicer already emitted. So the last word belongs here, and it is
deletion — the stance `splice` already takes on a citation of a chunk that was
never offered. A missing block reads as a gap; `[[1214-1215]]` reads as a bug.
"""

from __future__ import annotations

import re

__all__ = ["drop_unresolved"]

_LEFTOVER = re.compile(r"\s?\[\[[^\]\n]*\]\]")
r"""The leading `\s?` is taken too, so no sentence is left closing on " "."""


def drop_unresolved(text: str) -> str:
    """`text` without the bracket pairs every splicer left behind."""
    return _LEFTOVER.sub("", text)
