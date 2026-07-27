"""The signals that REWEIGHT the base score, one class each.

Adding a signal is one class and one entry in `LANES` — never surgery on a long
function, which is how a scoring path becomes the thing nobody dares touch.
"""

from __future__ import annotations

import numpy as np

from ..._arrays import Matrix
from ..intent import wants_tests
from ..paths import ident_tokens
from ._fusion import DenseFileFusion, neutral_score
from .context import QueryContext
from .lane import Base, Lane

__all__ = ["TestPenalty", "LexicalBoost", "BASE", "LANES"]


class TestPenalty:
    """Soft down-weight for test files: keep them reachable, stop them crowding.

    Tests quote the implementation's vocabulary by design, so they match nearly
    every query about it. Excluding them outright would lose the one place that
    shows a mechanism being USED; a penalty keeps them findable without letting
    them fill the answer.

    It STANDS DOWN when the question asked for tests. Applied blind it took the
    best-matching chunk in a repository — the four `halt` tests, rank #0 of
    2 700 by raw cosine — and delivered it at #115 for "where are the tests for
    halt?". A down-weight aimed at the thing the reader asked for is not a
    tie-break, it is an answer being withheld.

    And it scales the SIGNAL, not the score. Multiplying the fused score direct
    subtracted a flat 0.1125 — see `neutral_score` — which on a real task put a
    test file the retrieval had found at #7 of 285 down at #137, so the file the
    change had to edit never entered the bundle at all.
    """

    name = "test-penalty"

    def applies(self, ctx: QueryContext) -> bool:
        return not wants_tests(ctx.query)

    def apply(self, ctx: QueryContext, fused: Matrix) -> Matrix:
        floor = neutral_score(ctx.params)
        damped = floor + (fused - floor) * ctx.params.test_penalty
        return np.where(ctx.is_test, damped, fused)  # pyright: ignore[reportUnknownMemberType]


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


BASE: Base = DenseFileFusion()

# Order is load-bearing: the penalty applies to the fused base, and the lexical
# nudge lands last so it breaks ties rather than being scaled by anything after.
LANES: tuple[Lane, ...] = (TestPenalty(), LexicalBoost())
