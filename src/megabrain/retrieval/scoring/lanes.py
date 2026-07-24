"""The scoring signals themselves, one class each.

Adding a signal is one class and one entry in `LANES` — never surgery on a long
function, which is how a scoring path becomes the thing nobody dares touch.
"""

from __future__ import annotations

import numpy as np

from ..._arrays import Matrix
from ..paths import ident_tokens
from .context import QueryContext
from .lane import Lane

__all__ = ["DenseFileFusion", "TestPenalty", "LexicalBoost", "LANES"]


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

    def applies(self, ctx: QueryContext) -> bool:
        return True

    def apply(self, ctx: QueryContext, fused: Matrix | None) -> Matrix:
        dense = (ctx.chunks @ ctx.query_vector + 1) / 2
        by_file = (ctx.files @ ctx.query_vector + 1) / 2
        # A chunk whose file has no skeleton vector gets a neutral 0.5 rather
        # than 0: absence of a signal is not evidence against it.
        # `.astype` is not cosmetic: numpy promotes to float64 on mixed
        # arithmetic, and a promoted score array would silently double the
        # memory of the hottest structure in the engine.
        # numpy's `where` declares a partially unknown return in its shipped
        # overloads; suppressed by rule name at the exact line, never
        # package-wide — the declared return type is what pins this.
        blended = dense + ctx.params.file_fusion_w * np.where(  # pyright: ignore[reportUnknownMemberType]
            ctx.file_of >= 0, by_file[ctx.file_of], 0.5)
        return blended.astype(np.float32)


class TestPenalty:
    """Soft down-weight for test files: keep them reachable, stop them crowding.

    Tests quote the implementation's vocabulary by design, so they match nearly
    every query about it. Excluding them outright would lose the one place that
    shows a mechanism being USED; a penalty keeps them findable without letting
    them fill the answer.
    """

    name = "test-penalty"

    def applies(self, ctx: QueryContext) -> bool:
        return True

    def apply(self, ctx: QueryContext, fused: Matrix) -> Matrix:
        return np.where(ctx.is_test, fused * ctx.params.test_penalty, fused)  # pyright: ignore[reportUnknownMemberType]


class LexicalBoost:
    """An exact filename or symbol-name match, as an additive nudge.

    Small on purpose. It breaks ties in favour of the file a developer named,
    without letting a coincidental word match outrank real semantic relevance —
    a boost large enough to reorder the top would reinvent keyword search.
    """

    name = "lexical"

    def applies(self, ctx: QueryContext) -> bool:
        return bool(ctx.query_tokens)

    def apply(self, ctx: QueryContext, fused: Matrix) -> Matrix:
        p = ctx.params
        boost = np.zeros(len(ctx.metas), dtype=np.float32)
        for i, meta in enumerate(ctx.metas):
            stem = meta.file.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            by_file = len(ident_tokens(stem) & ctx.query_tokens)
            by_symbol = len(ident_tokens(meta.name or "") & ctx.query_tokens)
            boost[i] = max(p.file_boost_w * min(by_file, p.lexical_boost_cap),
                           p.sym_boost_w * min(by_symbol, p.lexical_boost_cap))
        return fused + boost


# Order is load-bearing: the penalty applies to the fused base, and the lexical
# nudge lands last so it breaks ties rather than being scaled by anything after.
LANES: tuple[Lane, ...] = (DenseFileFusion(), TestPenalty(), LexicalBoost())  # type: ignore[assignment]
