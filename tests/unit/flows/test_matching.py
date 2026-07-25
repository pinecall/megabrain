"""Matching: which cached flows a query pulls in, and how many.

One question can legitimately involve SEVERAL cached walkthroughs — "how does
auth talk to billing" is answered by the auth flow and the billing flow
together — so matching returns a small set, not a winner. The cap is what stops
a broad question dragging every flow in the index into the prompt.

Two lanes, and the separation is load-bearing: the ATTACH lane compares against
question+prose, because prose is what makes a paraphrase recognisable; the
SERVE lane compares against the question ALONE, so a long walkthrough can never
dilute the score of an identical question.
"""

from __future__ import annotations

import numpy as np

from megabrain.flows import match_flows
from megabrain.flows.match import FLOW_MIN_SIM, FLOW_TOP_K
from megabrain.storage.model import FlowMeta


def unit(*values: float) -> np.ndarray:
    raw = np.array(values, dtype=np.float32)
    return raw / np.linalg.norm(raw)


def meta(question: str) -> FlowMeta:
    return FlowMeta(id=1, question=question, text=f"the {question} walkthrough",
                    files={"a.py": "sha"})


def matrix(*vectors: np.ndarray) -> np.ndarray:
    return np.stack(vectors)


def test_several_flows_can_answer_ONE_question() -> None:
    """The case that makes this a set and not a lookup: a question that spans
    two subsystems is answered by both cached walkthroughs."""
    metas = [meta("how does auth work"), meta("how does billing work")]
    attach = matrix(unit(1, 0.9), unit(0.9, 1))
    matched = match_flows(metas, attach, attach, unit(1, 1))
    assert len(matched) == 2


def test_never_more_than_the_cap() -> None:
    """A broad question matches everything a little. Without the cap the whole
    cache lands in the prompt, and the walkthrough is written from a summary
    of summaries."""
    metas = [meta(f"flow {n}") for n in range(6)]
    attach = matrix(*[unit(1, 0.01 * n) for n in range(6)])
    assert len(match_flows(metas, attach, attach, unit(1, 0))) == FLOW_TOP_K


def test_the_best_match_comes_first() -> None:
    metas = [meta("distant"), meta("close")]
    attach = matrix(unit(1, -1), unit(1, 0.98))
    matched = match_flows(metas, attach, attach, unit(1, 1))
    assert matched[0]["question"] == "close"


def test_an_unrelated_flow_is_not_attached() -> None:
    """Below the floor nothing is attached at all: an irrelevant walkthrough in
    the prompt is worse than no context, because the model will use it."""
    metas = [meta("something else entirely")]
    attach = matrix(unit(1, 0))
    assert match_flows(metas, attach, attach, unit(-1, 0)) == []


def test_the_floor_is_the_documented_one() -> None:
    metas = [meta("borderline")]
    just_under = 2 * (FLOW_MIN_SIM - 0.02) - 1        # undo the (cos+1)/2 mapping
    attach = matrix(unit(1, 0))
    query = unit(just_under, float(np.sqrt(1 - just_under ** 2)))
    assert match_flows(metas, attach, attach, query) == []


def test_the_two_lanes_score_SEPARATELY() -> None:
    """The reason there are two vectors. A long walkthrough drags the
    question+prose vector away from the bare question; the serve lane is
    immune, so an identical question still scores ~1.0 there."""
    metas = [meta("how does retry work")]
    diluted_by_prose = matrix(unit(1, 1))            # attach lane
    the_question_alone = matrix(unit(1, 0))          # serve lane
    matched = match_flows(metas, diluted_by_prose, the_question_alone, unit(1, 0))
    assert matched[0]["qscore"] > matched[0]["score"]


def test_an_empty_cache_is_not_an_error() -> None:
    empty = np.zeros((0, 2), dtype=np.float32)
    assert match_flows([], empty, empty, unit(1, 0)) == []
