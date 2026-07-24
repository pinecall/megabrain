"""Everything the scoring lanes share for one query, computed once.

The lanes read from here and mutate only the score array threaded between them,
so a lane can never accidentally change what a later lane sees.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..._arrays import BoolMask, IndexArray, Matrix, Vector
from ...storage.model import ChunkMeta
from ..params import RetrievalParams
from ..paths import ident_tokens, is_test

__all__ = ["QueryContext", "build_context"]


@dataclass(frozen=True, slots=True)
class QueryContext:
    query: str
    params: RetrievalParams
    metas: list[ChunkMeta]      # candidate chunks, aligned with `chunks`
    chunks: Matrix
    files: Matrix
    query_vector: Vector
    file_of: IndexArray         # chunk index -> file row, or -1 when absent
    is_test: BoolMask           # per-chunk test-file mask
    query_tokens: set[str]


def build_context(*, query: str, params: RetrievalParams, metas: list[ChunkMeta],
                  chunks: Matrix, file_paths: list[str], files: Matrix,
                  query_vector: Vector) -> QueryContext:
    """Precompute the per-chunk lookups every lane would otherwise redo.

    `file_of` is the join between the two matrices. Built once here because
    doing it inside a lane makes it O(lanes) for no reason, and because a lane
    computing its own join is a lane that can disagree with another one.
    """
    row_of = {path: i for i, path in enumerate(file_paths)}
    return QueryContext(
        query=query,
        params=params,
        metas=metas,
        chunks=chunks,
        files=files,
        query_vector=query_vector,
        file_of=np.array([row_of.get(m.file, -1) for m in metas], dtype=np.int64),
        is_test=np.array([is_test(m.file) for m in metas], dtype=bool),
        query_tokens=ident_tokens(query),
    )
