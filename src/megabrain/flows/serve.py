"""Deciding whether a cached answer may be returned AS the answer.

Three conditions, and every one of them has a failure behind it:

  the question matches nearly exactly   - on the SERVE lane, so a long
                                          walkthrough cannot dilute it
  the cached question COVERS the query  - cosine is symmetric, "answers
                                          everything you asked" is not
  every cited file is unchanged ON DISK - a walkthrough must not outlive the
                                          code it describes

Miss any one and the flow is still useful, just not as the whole answer: it
gets attached as context and the narrator writes fresh.
"""

from __future__ import annotations

from pathlib import Path

from ..contracts import FlowHit
from .covers import covers
from .freshness import files_current
from .match import FLOW_SERVE_SIM

__all__ = ["serve_verbatim"]


def serve_verbatim(root: Path | str, flows: list[FlowHit],
                   question: str) -> FlowHit | None:
    """The flow that may be returned verbatim, or None."""
    for flow in flows:
        if flow["qscore"] < FLOW_SERVE_SIM:
            continue
        if question and not covers(question, flow["question"]):
            continue
        if files_current(root, flow["sha"]):
            return flow
    return None
