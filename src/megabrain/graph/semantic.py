"""The semantic lane: edges the imports never wrote.

Two files can implement the same idea and never mention each other, and no
amount of structure will show it. The skeleton vectors already exist — retrieval
built them — so the cosine between them is a second edge type for free.

Sparse on purpose. Every file keeping its three closest twins above a floor is a
graph a person can read; every pair above the floor is a hairball. The full
cosine matrix is never RETAINED either: at 10 000 files it is 400 MB of float32,
so the pairs the surprises need are extracted while each block of rows exists
and the block is then discarded.
"""

from __future__ import annotations

from typing import cast

import numpy as np

from .._arrays import Matrix

__all__ = ["semantic_lane", "SEM_EDGE_MIN", "SEM_TOP_K", "SURPRISE_MIN"]

SEM_EDGE_MIN = 0.80   # min cosine for a semantic edge
SEM_TOP_K = 3         # semantic edges per node — keeps the graph sparse

# Stricter than a mere semantic edge: a surprise is an ACCUSATION, and it had
# better be sure. Lives beside the other cosine floors because the candidates
# are found HERE, where the cosines briefly exist.
SURPRISE_MIN = 0.85

_BLOCK = 512          # rows of cosines alive at once: block × n, never n × n

Twin = tuple[str, str, float]


def semantic_lane(
    files: list[str], vec_paths: list[str], vectors: Matrix,
) -> tuple[dict[str, dict[str, float]], list[Twin]]:
    """(per-file top-k neighbours, every pair above the surprise floor).

    Every file gets an entry — empty when it has no vector or no close twin — so
    a reader can iterate without existence checks. The twins come back as pairs
    rather than a matrix: they are the only thing downstream that needed every
    cosine, and above 0.85 they are rare enough to list.
    """
    sem: dict[str, dict[str, float]] = {relpath: {} for relpath in files}
    order = [path for path in vec_paths if path in sem]
    if len(order) < 2 or not vectors.size:
        return sem, []
    unit = _units(vectors, {p: i for i, p in enumerate(vec_paths)}, order)
    twins: list[Twin] = []
    for start in range(0, len(order), _BLOCK):
        _scan(sem, twins, order, unit, start)
    return sem, twins


def _scan(sem: dict[str, dict[str, float]], twins: list[Twin],
          order: list[str], unit: Matrix, start: int) -> None:
    """One block of rows: top-k edges kept, twin pairs above the floor listed."""
    block = cast("Matrix", (unit[start:start + _BLOCK] @ unit.T).astype(np.float32))  # pyright: ignore[reportUnknownMemberType]
    for local in range(block.shape[0]):
        row, path = block[local], order[start + local]
        # A file is its own nearest neighbour at 1.0, which would fill every
        # top-k slot with self-edges and leave the lane empty.
        row[start + local] = -1.0
        for other in np.argsort(-row, kind="stable")[:SEM_TOP_K]:  # pyright: ignore[reportUnknownMemberType]
            score = float(row[int(other)])
            if score >= SEM_EDGE_MIN:
                twin = order[int(other)]
                sem[path][twin] = max(sem[path].get(twin, 0.0), score)
                sem[twin][path] = max(sem[twin].get(path, 0.0), score)
        for other in np.nonzero(row >= SURPRISE_MIN)[0]:  # pyright: ignore[reportUnknownMemberType]
            if start + local < int(other):        # each unordered pair ONCE
                twins.append((path, order[int(other)], float(row[int(other)])))


def _units(vectors: Matrix, rows: dict[str, int], order: list[str]) -> Matrix:
    kept = vectors[[rows[path] for path in order]]
    norms: Matrix = np.linalg.norm(kept, axis=1, keepdims=True)  # pyright: ignore[reportUnknownMemberType]
    safe: Matrix = np.where(norms == 0, 1, norms)  # pyright: ignore[reportUnknownMemberType]
    return kept / safe
