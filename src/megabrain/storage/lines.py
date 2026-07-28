"""A file reassembled from its chunks — an exact line partition, so the
concatenation is the file.

Lives beside the other Store readers because that is all it is: both verbs
quote lines through it (`ask` when splicing a citation, `grep` when reading a
site's body), and while it sat inside `ask/` the shared read forced `grep` to
import the package it deliberately moved out of.
"""

from __future__ import annotations

from .store import Store

__all__ = ["lines_of"]


def lines_of(store: Store, path: str) -> list[str]:
    """The file's lines from the index — an exact partition, in line order."""
    metas = store.chunks.read_file(path)
    lines: list[str] = []
    for meta in sorted(metas, key=lambda m: m.start_line):
        lines.extend((meta.text or "").split("\n"))
    return lines
