"""The two recall lanes' contracts: flows and anchors.

Apart from the bundle because they are a different KIND of member: the tiers
are the ranking's opinion, these are pure ADDITIONS from the caches and floors,
and the split keeps "what ranked" and "what was appended regardless" readable
as separate promises.
"""

from __future__ import annotations

from typing import TypedDict

from .chunk import Span

__all__ = ["FlowHit", "AnchorHit"]


class FlowHit(TypedDict):
    """A cached ask synthesis that matched. `sha` pins the code it described,
    so a flow dies with the source it cited."""

    question: str
    text: str
    files: list[str]
    sha: dict[str, str]
    score: float                  # question+prose similarity (ATTACH lane)
    qscore: float                 # question-only similarity (SERVE lane)


class AnchorHit(Span):
    """A chunk the lexical anchor floor pulled in: a rare identifier the query
    quoted lives verbatim in its text. A pure addition — never displaces."""

    terms: list[str]
