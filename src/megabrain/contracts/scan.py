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
    ignore: list[str]        # the patterns in effect, from .megabrain.json
