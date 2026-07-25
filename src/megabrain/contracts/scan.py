"""The census: what indexing WOULD do, before it costs anything.

Every skip carries its reason. A file that quietly vanished from an index is
the hardest kind of bug to notice — the search simply never returns it, and
nothing anywhere reports an error — so the census exists to make the decision
inspectable before the money is spent.
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["SkippedFile", "ScanReport"]


class SkippedFile(TypedDict):
    file: str
    reason: str              # excluded | too-big | unreadable


class ScanReport(TypedDict):
    path: str
    name: str
    indexed: bool            # is there already an index at this path
    would_index: int
    skipped: list[SkippedFile]
    by_extension: dict[str, int]
    ignore: list[str]        # the patterns in effect, from megabrain.json
    supported: list[str]     # the extensions THIS build can read
    unsupported: dict[str, int]
    """Source files walked past because no chunker claims their extension.

    The answer to "why is this census empty", given where the question is asked.
    Data files are left out of it — `package.json` in the list turns the finding
    into noise, and what matters is the SOURCE this build cannot read.
    """
