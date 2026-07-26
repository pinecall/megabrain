"""Phase 3 — write the pass to the index, in one transaction.

Reached only once every embedding has come back, which gives a property worth
having for free: a network failure aborts BEFORE any row is touched, so the
previous index survives intact rather than half-replaced.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ..._arrays import Matrix, Vector
from ...storage import Store
from .embed import Vectors
from .plan import Planned

__all__ = ["write_files", "prune_orphans"]


def write_files(store: Store, pending: Sequence[Planned],
                vectors: Sequence[Vectors]) -> int:
    """Replace each changed file's rows. Returns the number of chunks written."""
    written = 0
    for item, vecs in zip(pending, vectors):
        # Not `drop_incoming`: this file is being re-indexed, not removed, so
        # the edges pointing AT it are still true. Dropping them here destroys
        # every edge whose source happened to be processed earlier in this pass.
        store.files.delete(item.relpath, drop_incoming=False)
        store.chunks.insert(item.result.chunks, _matrix(vecs.chunks))
        store.symbols.insert(item.result.symbols)
        store.files.upsert(item.relpath, item.sha, item.result.skeleton, vecs.skeleton)
        written += len(item.result.chunks)
    return written


def prune_orphans(store: Store, present: set[str], skipped: set[str]) -> int:
    """Drop indexed files this pass did not index — telling GONE from SKIPPED.

    Both lose their rows: whatever the reason, this pass could not confirm what
    they contain, and stale chunks answer as confidently as fresh ones.

    Only a file that is genuinely gone loses its INCOMING edges. A skipped file
    still exists, so the imports pointing at it are still true — and those edges
    belong to other files, which did nothing wrong. Treating "too big today" as
    "deleted" silently tore arcs out of the graph.
    """
    indexed = store.files.all_paths()
    for relpath in indexed - present - skipped:
        store.files.delete(relpath, drop_incoming=True)
    for relpath in indexed & skipped:
        store.files.delete(relpath, drop_incoming=False)
    return len(indexed - present)


def _matrix(vectors: Sequence[Vector]) -> Matrix | None:
    """Stack a file's chunk vectors, or None when it produced no chunks."""
    if not vectors:
        return None
    # numpy's `stack` declares a partially unknown return in its shipped
    # overloads; suppressed by rule name at the exact line, never package-wide.
    return np.stack(vectors)      # pyright: ignore[reportUnknownMemberType]
