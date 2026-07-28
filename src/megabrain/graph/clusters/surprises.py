"""Surprises: semantically twins, structurally strangers.

The one thing on the map nobody asks for by name and everybody stops at. Three
legs, each excluding something: an edge between the pair means it is not a
surprise, the same community means the clustering already knows, and low
similarity means there is nothing to report. What is left is a pair the repo
treats as unrelated and the embedding space swears is the same idea — a
duplicated mechanism, a candidate refactor, or a vendored copy.
"""

from __future__ import annotations

from ...contracts import Surprise
from ..build import RepoGraph
from ..semantic import SURPRISE_MIN

__all__ = ["surprises_of", "SURPRISE_MIN", "SURPRISE_TOP"]

SURPRISE_TOP = 10


def surprises_of(graph: RepoGraph, communities: dict[str, int]) -> list[Surprise]:
    """The strongest unconnected twins across community lines.

    The candidates arrive on the graph already above `SURPRISE_MIN` — collected
    by the semantic lane while the cosines existed — so the two legs left to
    check here are the two that need the rest of the graph: no edge between the
    pair, and different communities.
    """
    found = [Surprise(a=left, b=right, score=round(score, 3))
             for left, right, score in graph.twins
             if right not in graph.near.get(left, {})
             and communities.get(left) != communities.get(right)]
    found.sort(key=lambda entry: (-entry["score"], entry["a"]))
    return found[:SURPRISE_TOP]
