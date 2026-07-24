"""Real indexes for retrieval tests — a Store on disk, not a hand-built state.

Retrieval bugs live in the joins between the two matrices and the tables, and
a hand-assembled state is exactly where those joins are assumed rather than
exercised.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Sequence

import numpy as np

from megabrain._arrays import Vector
from megabrain.retrieval.bundle._rank import Ranking
from megabrain.retrieval.params import DEFAULT_PARAMS
from megabrain.retrieval.state import SearchState
from megabrain.storage import Store
from tests.unit.storage.factories import chunk, symbol

__all__ = ["StubEmbedder", "state_for", "small_index", "index_without_skeletons",
           "tied_neighbours"]

DIMS = 4


class StubEmbedder:
    """Every text at the same point: scores tie, which is where the bugs are."""

    model = "stub"

    def embed(self, texts: Sequence[str], *, on_batch: object = None) -> list[Vector]:
        return [np.ones(DIMS, dtype=np.float32) / 2.0 for _ in texts]


def state_for(root: Path) -> SearchState:
    """A warm state over an index already written at `root`."""
    store = Store(root)
    metas, chunks = store.chunks.read_matrix()
    paths, skeletons, files = store.files.read_matrix()
    return SearchState(store=store, embedder=StubEmbedder(),  # type: ignore[arg-type]
                       metas=metas, chunks=chunks, file_paths=paths,
                       file_skeletons=skeletons, files=files, repo=root.name)


def small_index(root: Path, *, skeleton_vectors: bool = True) -> SearchState:
    """Two files, three chunks, symbols with decorators — the shape the
    contract test needs, and enough of a join for the scoring lanes."""
    skel: Vector | None = np.ones(DIMS, np.float32) if skeleton_vectors else None
    with Store(root) as store:
        store.chunks.insert(
            [chunk("svc.py", cid=1, start=1, end=10, name="Service.handle"),
             chunk("svc.py", cid=2, start=11, end=20, name="Service.close"),
             chunk("util.py", cid=3, start=1, end=8, name="helper")],
            np.eye(3, DIMS, dtype=np.float32))
        store.symbols.insert([symbol("svc.py", name="Service.handle",
                                     decorators=("property",)),
                              symbol("util.py", name="helper")])
        store.files.upsert("svc.py", "sha-a", "class Service", skel)
        store.files.upsert("util.py", "sha-b", "def helper", skel)
    return state_for(root)


def index_without_skeletons(root: Path) -> SearchState:
    """Chunks embedded, skeletons not: the file matrix is empty."""
    return small_index(root, skeleton_vectors=False)


def tied_neighbours() -> list[str]:
    """The graph neighbours of one file, all scoring identically.

    Printed by a subprocess under two hash seeds: with a tie-break that is not
    total, this is a different list in each process.
    """
    from megabrain.retrieval.bundle._related import neighbours_of

    names = [f"n{i}.py" for i in range(8)]
    root = Path(tempfile.mkdtemp())
    with Store(root) as store:
        store.graph.replace_edges("a.py", [(n, "import") for n in names])
    state = state_for(root)
    ranking = Ranking(order=["a.py", *names], chunks_of={},
                      best_of={"a.py": 1.0, **dict.fromkeys(names, 0.5)})
    try:
        return neighbours_of(state, ["a.py"], ranking, DEFAULT_PARAMS)
    finally:
        state.close()
