"""Phase 3 — write the pass to the index, in one transaction.

Reached only once every embedding has come back, which gives a property worth
having for free: a network failure aborts BEFORE any row is touched, so the
previous index survives intact rather than half-replaced.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ..storage import Store
from ._embed import Vectors
from ._plan import Planned

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


def prune_orphans(store: Store, present: set[str]) -> int:
    """Drop files that are indexed but no longer on disk.

    Here — and only here — incoming edges go too: a file that does not exist
    cannot be a valid import target, so an edge pointing at it is a lie the
    graph would otherwise keep telling.
    """
    gone = store.files.all_paths() - present
    for relpath in gone:
        store.files.delete(relpath, drop_incoming=True)
    return len(gone)


def _matrix(vectors: Sequence[object]):      # type: ignore[no-untyped-def]
    """Stack a file's chunk vectors, or None when it produced no chunks."""
    return np.stack(vectors) if vectors else None      # type: ignore[arg-type]
