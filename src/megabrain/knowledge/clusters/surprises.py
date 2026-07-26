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

__all__ = ["surprises_of", "SURPRISE_MIN", "SURPRISE_TOP"]

# Stricter than a mere semantic edge: a surprise is an ACCUSATION, and it had
# better be sure.
SURPRISE_MIN = 0.85
SURPRISE_TOP = 10


def surprises_of(graph: RepoGraph, communities: dict[str, int]) -> list[Surprise]:
    """The strongest unconnected twins across community lines."""
    if graph.sims is None:
        return []
    found: list[Surprise] = []
    order = graph.sim_files
    for i, left in enumerate(order):
        for j in range(i + 1, len(order)):
            right = order[j]
            score = float(graph.sims[i, j])
            if (score >= SURPRISE_MIN
                    and right not in graph.near.get(left, {})
                    and communities.get(left) != communities.get(right)):
                found.append(Surprise(a=left, b=right, score=round(score, 3)))
    found.sort(key=lambda entry: (-entry["score"], entry["a"]))
    return found[:SURPRISE_TOP]
