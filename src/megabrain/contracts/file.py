"""Reading one file, or one symbol out of it.

The answer to "you pointed me at this — now show me". Every RELATED entry in a
bundle is a pointer, so this is the other half of that map, and it returns the
INDEXED text: what search actually ranked, not whatever the working tree looks
like a minute later.
"""

from __future__ import annotations

from typing import TypedDict

from .chunk import SymbolRef

__all__ = ["FileView"]


class FileView(TypedDict):
    """One file, or the span of one symbol inside it."""

    file: str
    start_line: int
    end_line: int
    text: str
    symbols: list[SymbolRef]     # the outline of the WHOLE file, always
    symbol: str | None           # the name that narrowed it, if any
    stale: bool
    """True when the file on disk no longer matches what was indexed.

    Said out loud rather than silently re-reading disk: the lines a bundle
    pointed at were the indexed ones, and a view that quietly serves newer
    text would answer a question about code the ranking never saw.
    """
