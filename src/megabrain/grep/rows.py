"""One file's block of the render: heading, what is in scope, then its rows.

Split from resolving WHICH sites there are because it answers a different
question — what the reader needs on screen to stop opening files to orient
themselves.

The `in scope` line is METADATA, not code, so it does not break the rule `grep`
exists for. It is here because it was the biggest measured cost of the render
without it: a reader handed correct rows for every site still spent three of
twenty calls asking "is this name already imported?" — two Reads, and one Edit
it had to undo when the answer turned out to be no.
"""

from __future__ import annotations

from ..storage import Store
from .surface import import_surface

__all__ = ["rendered"]


def rendered(store: Store, path: str, rows: list[tuple[int, int, str]]) -> str:
    """`## path`, its import surface, and its rows in line order."""
    surface = import_surface(store, path)
    scope = f"  in scope: {surface}\n" if surface else ""
    body = "\n".join(f"  L{low}-{high}  {label}" for low, high, label in sorted(rows))
    return f"## {path}\n{scope}{body}\n\n"
