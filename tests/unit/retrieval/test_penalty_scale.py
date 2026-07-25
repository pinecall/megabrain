"""A multiplicative penalty on an OFFSET score is not the penalty it claims.

FOUND IN USE, and it is the reason `megabrain_search` returned the same number
of turns as `grep` on a real task. Asked to "add a redirect_back helper that
redirects to the Referer header with a fallback", the two files that had to be
EDITED were `lib/sinatra/base.rb` and `test/helpers_test.rb`. Decomposed lane
by lane over 285 chunks:

    cosine crudo        helpers_test #7     base.rb  #9
    + file fusion       helpers_test #7     base.rb #16
    + test penalty      helpers_test #137   base.rb  #9     <-- here
    + lexical (full)    helpers_test #141   base.rb  #5

The retrieval FOUND the test file at #7 of 285. One lane put it at #137, so it
never entered the bundle and the agent went looking for it by hand.

The arithmetic, and it is not a tuning problem:

    fused = (cos + 1)/2 + w * (file_cos + 1)/2        w = 0.5

A chunk with cosine ZERO already scores 0.75. Multiplying by 0.85 removes
0.1125 of absolute score — while the entire span between a zero-cosine chunk
and the best chunk in the repository, on this query, is about 0.24. A "soft 15%
down-weight" erases HALF the dynamic range, and it erases the same 0.1125 from
a perfect match as from a random one.

So the penalty applies to the SIGNAL — the distance above the neutral floor a
scoreless chunk already sits at — which is what makes 0.85 mean what its
docstring has always said it means.
"""

from __future__ import annotations

import numpy as np

from megabrain.retrieval.params import DEFAULT_PARAMS, RetrievalParams
from megabrain.retrieval.scoring._fusion import neutral_score
from megabrain.retrieval.scoring.lanes import TestPenalty


class Ctx:
    """The two fields the penalty reads, and nothing else."""

    def __init__(self, is_test: list[bool], params: RetrievalParams) -> None:
        self.is_test = np.array(is_test)
        self.params = params
        self.query = "add a helper"


def test_a_scoreless_chunk_is_the_neutral_floor() -> None:
    """The number the whole bug turns on: fusion maps a zero cosine to 0.75,
    not to 0."""
    assert neutral_score(DEFAULT_PARAMS) == 0.75


def test_the_penalty_leaves_a_SCORELESS_test_untouched() -> None:
    """It has no signal to remove. Taking 0.1125 off it was taking away the
    offset, which is not evidence about anything."""
    fused = np.array([neutral_score(DEFAULT_PARAMS)], dtype=np.float32)
    out = TestPenalty().apply(Ctx([True], DEFAULT_PARAMS), fused)
    assert abs(float(out[0]) - neutral_score(DEFAULT_PARAMS)) < 1e-6


def test_the_penalty_removes_15_PERCENT_OF_THE_SIGNAL() -> None:
    """Not 15% of the score. A test chunk twice as good as neutral keeps 85% of
    what makes it good, which is the only reading under which `0.85` and the
    word "soft" describe the same thing."""
    floor = neutral_score(DEFAULT_PARAMS)
    fused = np.array([floor + 0.20], dtype=np.float32)
    out = TestPenalty().apply(Ctx([True], DEFAULT_PARAMS), fused)
    assert abs(float(out[0]) - (floor + 0.20 * 0.85)) < 1e-6


def test_a_STRONG_test_still_outranks_a_WEAK_implementation_file() -> None:
    """The regression, as an ordering. Under the old arithmetic the penalty was
    a flat 0.1125 that a strong match could not survive, so a test file that
    matched twice as well as an implementation file still lost to it."""
    floor = neutral_score(DEFAULT_PARAMS)
    fused = np.array([floor + 0.20, floor + 0.12], dtype=np.float32)   # test, impl
    out = TestPenalty().apply(Ctx([True, False], DEFAULT_PARAMS), fused)
    assert out[0] > out[1], "a much better test lost to a mediocre implementation"


def test_it_still_LOSES_a_tie_against_an_equal_implementation() -> None:
    """The penalty must keep doing its job: tests quote the implementation's
    vocabulary, so at equal evidence the implementation is what was asked for."""
    floor = neutral_score(DEFAULT_PARAMS)
    fused = np.array([floor + 0.15, floor + 0.15], dtype=np.float32)
    out = TestPenalty().apply(Ctx([True, False], DEFAULT_PARAMS), fused)
    assert out[0] < out[1]


def test_the_floor_FOLLOWS_the_fusion_weight() -> None:
    """Hardcoding 0.75 in the penalty would make the two drift the moment
    anyone tuned the fusion, and the drift would be invisible — a wrong floor
    is still a plausible-looking score."""
    assert neutral_score(RetrievalParams(file_fusion_w=0.0)) == 0.5
    assert neutral_score(RetrievalParams(file_fusion_w=1.0)) == 1.0
