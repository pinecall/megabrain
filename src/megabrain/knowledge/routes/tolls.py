"""What it costs to route THROUGH a file.

Separated from the routing itself because it is the part with an opinion in it.
Dijkstra is a textbook; the toll table is the judgement about which files
explain a connection and which merely carry it, and it deserves to be read on
its own.
"""

from __future__ import annotations

from ...retrieval.paths import is_test
from ..build import RepoGraph

__all__ = ["tolls_of", "PLUMBING_TOLL", "HUB_TOLL", "HUB_MIN"]

PLUMBING_TOLL = 4
"""Charged by NAME, not by degree.

A package `__init__.py` is plumbing in a five-file repository too, and degree
cannot see that when the repository is small. Same for a test file: it imports
both sides by design, which makes it the cheapest route and the least
informative one.
"""

HUB_TOLL = 3
HUB_MIN = 8
"""The floor under the p90 degree.

Degree is relative, so the threshold has to be too — but on a tiny repository
the p90 is 2 and everything looks like a hub, so the floor stops the toll from
firing on a graph that has no hubs at all.
"""


def tolls_of(graph: RepoGraph, exempt: tuple[str, ...] = ()) -> dict[str, int]:
    """relpath -> extra cost to pass through it. Absent means free.

    `exempt` is the route's endpoints: you asked for them, so being a hub is
    not a reason to charge you. Without this, "how does anything reach the
    logger" answers with a detour around the logger.
    """
    floor = _hub_floor(graph)
    tolls: dict[str, int] = {}
    for relpath in graph.files:
        if relpath in exempt:
            continue
        toll = PLUMBING_TOLL if _is_plumbing(relpath) else 0
        degree = graph.degree(relpath)
        if degree > floor:
            # Scaled, not flat: every edge past the floor adds cost, so the
            # 500-dependent module is a worse transit stop than the 20.
            toll += HUB_TOLL + (degree - floor)
        if toll:
            tolls[relpath] = toll
    return tolls


def _hub_floor(graph: RepoGraph) -> int:
    degrees = sorted(graph.degree(relpath) for relpath in graph.files)
    p90 = degrees[int(len(degrees) * 0.90)] if degrees else 0
    return max(HUB_MIN, p90)


def _is_plumbing(relpath: str) -> bool:
    return relpath.rsplit("/", 1)[-1] == "__init__.py" or is_test(relpath)
