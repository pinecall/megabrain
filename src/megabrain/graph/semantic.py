"""The semantic lane: edges the imports never wrote.

Two files can implement the same idea and never mention each other, and no
amount of structure will show it. The skeleton vectors already exist — retrieval
built them — so the cosine between them is a second edge type for free.

Sparse on purpose. Every file keeping its three closest twins above a floor is a
graph a person can read; every pair above the floor is a hairball.
"""

from __future__ import annotations

from typing import cast

import numpy as np

from .._arrays import Matrix

__all__ = ["semantic_lane", "SEM_EDGE_MIN", "SEM_TOP_K"]

SEM_EDGE_MIN = 0.80   # min cosine for a semantic edge
SEM_TOP_K = 3         # semantic edges per node — keeps the graph sparse


def semantic_lane(
    files: list[str], vec_paths: list[str], vectors: Matrix,
) -> tuple[dict[str, dict[str, float]], Matrix | None, list[str]]:
    """(per-file top-k neighbours, the full cosine matrix, the matrix's order).

    Every file gets an entry — empty when it has no vector or no close twin — so
    a reader can iterate without existence checks. The full matrix comes back
    too, because SURPRISES need every pair and the top-k lane deliberately
    forgot the rest.
    """
    sem: dict[str, dict[str, float]] = {relpath: {} for relpath in files}
    order = [path for path in vec_paths if path in sem]
    if len(order) < 2 or not vectors.size:
        return sem, None, []
    sims = _cosines(vectors, {p: i for i, p in enumerate(vec_paths)}, order)
    for index, path in enumerate(order):
        for other in np.argsort(-sims[index], kind="stable")[:SEM_TOP_K]:  # pyright: ignore[reportUnknownMemberType]
            score = float(sims[index, int(other)])
            if score >= SEM_EDGE_MIN:
                twin = order[int(other)]
                sem[path][twin] = max(sem[path].get(twin, 0.0), score)
                sem[twin][path] = max(sem[twin].get(path, 0.0), score)
    return sem, sims.astype(np.float32), order


def _cosines(vectors: Matrix, rows: dict[str, int], order: list[str]) -> Matrix:
    kept = vectors[[rows[path] for path in order]]
    norms: Matrix = np.linalg.norm(kept, axis=1, keepdims=True)  # pyright: ignore[reportUnknownMemberType]
    safe: Matrix = np.where(norms == 0, 1, norms)  # pyright: ignore[reportUnknownMemberType]
    unit: Matrix = kept / safe
    # `unit.T` resolves to Unknown against numpy's shipped stubs, and the
    # matmul inherits it. `cast` states what the operation produces — the shape
    # is (n, n) by construction, and every reader of `sims` below indexes it as
    # exactly that.
    sims = cast("Matrix", (unit @ unit.T).astype(np.float32))  # pyright: ignore[reportUnknownMemberType]
    # A file is its own nearest neighbour at 1.0, which would fill every top-k
    # slot with self-edges and leave the lane empty.
    np.fill_diagonal(sims, -1.0)
    return sims
