"""Which cached flows a query pulls in. Pure cosine — no model on this path.

Two lanes, because one question has two different relationships with a cached
answer:

  ATTACH  question+prose. Prose is what makes a paraphrase recognisable, so
          this is the lane that finds "the same workflow, asked differently".
  SERVE   the question ALONE. An identical question scores ~1.0 here however
          long the walkthrough grew — prose length can never dilute it.

The cap matters as much as the floor: a broad question matches everything a
little, and without it the whole cache lands in the prompt and the walkthrough
gets written from a summary of summaries.
"""

from __future__ import annotations

import numpy as np

from .._arrays import Matrix, Vector
from ..contracts import FlowHit
from ..storage.model import FlowMeta

__all__ = ["match_flows", "FLOW_MIN_SIM", "FLOW_SERVE_SIM", "FLOW_TOP_K",
           "FLOW_DEDUP_SIM"]

FLOW_MIN_SIM = 0.62     # normalised (cos+1)/2 floor to ATTACH a flow as context
FLOW_SERVE_SIM = 0.88   # near-exact question -> serve the cached answer, no LLM
FLOW_TOP_K = 2          # at most this many flows per query
FLOW_DEDUP_SIM = 0.92   # same question asked twice -> replace, do not accumulate


def match_flows(metas: list[FlowMeta], attach: Matrix, serve: Matrix,
                query: Vector) -> list[FlowHit]:
    """The best few flows above the floor, each carrying BOTH scores.

    Several can match one question, and that is the point: a query spanning two
    subsystems is answered by both cached walkthroughs together.
    """
    if not metas or not attach.size:
        return []
    scores = (attach @ query + 1) / 2
    qscores = (serve @ query + 1) / 2 if serve.size else np.zeros_like(scores)
    out: list[FlowHit] = []
    # Stable, like every other ranking here: ties must not reshuffle between
    # runs, or two identical asks attach different context.
    for index in np.argsort(-scores, kind="stable")[:FLOW_TOP_K]:  # pyright: ignore[reportUnknownMemberType]
        position = int(index)
        if scores[position] < FLOW_MIN_SIM:
            break
        out.append(_hit(metas[position], float(scores[position]),
                        float(qscores[position])))
    return out


def _hit(meta: FlowMeta, score: float, qscore: float) -> FlowHit:
    return FlowHit(question=meta.question, text=meta.text,
                   files=sorted(meta.files), sha=meta.files,
                   score=round(score, 4), qscore=round(qscore, 4))
