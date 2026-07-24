"""The BASE signal: the only lane that creates the score array.

Alone in its own module because it is the one signal with a different shape —
everything in `lanes.py` reweights what this produces, and the two are not
interchangeable however similar they look from the pipeline.
"""

from __future__ import annotations

import numpy as np

from ..._arrays import Matrix
from .context import QueryContext

__all__ = ["DenseFileFusion"]


class DenseFileFusion:
    """Base relevance: chunk cosine fused with the cosine of its whole file.

    A chunk is judged partly by the company it keeps. A short helper inside the
    right file beats an eloquent chunk inside an unrelated one, which is what
    stops a well-worded comment somewhere else from outranking the code that
    actually answers the question.

    Cosines are mapped from [-1, 1] to [0, 1] so the fusion weight means the
    same thing across the range and later additive bonuses keep their scale.
    """

    name = "dense+file"

    def apply(self, ctx: QueryContext) -> Matrix:
        # `.astype` is not cosmetic: numpy promotes to float64 on mixed
        # arithmetic, and a promoted score array would silently double the
        # memory of the hottest structure in the engine.
        dense = (ctx.chunks @ ctx.query_vector + 1) / 2
        return (dense + ctx.params.file_fusion_w * _file_signal(ctx)).astype(np.float32)


def _file_signal(ctx: QueryContext) -> Matrix:
    """Each chunk's file-level cosine, or a neutral 0.5 where there is none.

    Absence of a signal is not evidence against a chunk, so a file with no
    skeleton vector scores neutral rather than zero — and an index with NO
    skeletons at all is that same case for every chunk. It has to be caught
    before the matmul: an empty file matrix does not broadcast against the
    query vector, so the whole query died with a shape error on an index that
    was merely incomplete.
    """
    if not ctx.files.size:
        return np.full(len(ctx.metas), 0.5, dtype=np.float32)
    by_file = (ctx.files @ ctx.query_vector + 1) / 2
    # numpy's `where` declares a partially unknown return in its shipped
    # overloads; suppressed by rule name at the exact line, never package-wide.
    return np.where(ctx.file_of >= 0, by_file[ctx.file_of], 0.5)  # pyright: ignore[reportUnknownMemberType]
