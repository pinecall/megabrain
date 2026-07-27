"""How two files are connected.

The question a dependency graph answers that nothing else can: not "are these
related" — search answers that — but "through WHAT", which is the chain
somebody has to read before changing either end.

Transit is COSTED, not merely ordered. A file imported by half the repository
(a logger, a config, a package `__init__`) connects ANY pair through
infrastructure rather than through a relationship, and plain breadth-first
search cannot tell the difference — checked live against a general-purpose
graph library, whose unweighted shortest-path routes through the single
highest-degree node in its own graph. So hubs, package plumbing and test files
pay a toll, semantic edges cost more than structural ones, and the endpoints
are exempt because you asked for them.
"""

from __future__ import annotations

import heapq

from ...contracts import Hop
from ..build import RepoGraph
from .tolls import tolls_of

__all__ = ["shortest_path", "STRUCT_COST", "SEM_COST"]

STRUCT_COST = 2   # a fact about execution
SEM_COST = 3      # an opinion about wording — same hop, more expensive


def shortest_path(graph: RepoGraph, source: str, target: str) -> list[Hop]:
    """The cheapest route from `source` to `target`, or [] if unconnected.

    Undirected: "how are these two connected" is not a question about
    direction, and answering it directionally hides the common case where two
    files meet at a third that imports them both.

    Each hop carries the `via` it crossed — `import`, `call`, `import/call`, or
    `semantic 0.91`. A route without its reasons is a list of filenames.
    """
    if source not in graph.near or target not in graph.near:
        return []
    if source == target:
        return [{"file": source, "via": ""}]
    toll = tolls_of(graph, exempt=(source, target))
    came_from = _dijkstra(graph, source, target, toll)
    if target not in came_from:
        return []
    return _walk_back(came_from, source, target)


def _dijkstra(graph: RepoGraph, source: str, target: str,
              toll: dict[str, int]) -> dict[str, tuple[str, str]]:
    """file -> (previous file, the edge crossed to reach it).

    Deterministic: the heap breaks ties on the filename, so two equal-cost
    routes never alternate between runs. A map that reshuffles is a map nobody
    trusts twice.
    """
    best: dict[str, float] = {source: 0.0}
    came_from: dict[str, tuple[str, str]] = {source: (source, "")}
    heap: list[tuple[float, str]] = [(0.0, source)]
    done: set[str] = set()
    while heap:
        cost, current = heapq.heappop(heap)
        if current in done:
            continue
        done.add(current)
        if current == target:
            break
        for neighbour, via, price in _edges(graph, current):
            walked = cost + price + toll.get(neighbour, 0)
            if walked < best.get(neighbour, float("inf")):
                best[neighbour] = walked
                came_from[neighbour] = (current, via)
                heapq.heappush(heap, (walked, neighbour))
    return came_from


def _edges(graph: RepoGraph, relpath: str) -> list[tuple[str, str, int]]:
    """Both lanes out of one file, in filename order for determinism."""
    structural = [(other, "/".join(sorted(kinds)), STRUCT_COST)
                  for other, kinds in sorted(graph.near.get(relpath, {}).items())]
    semantic = [(other, f"semantic {score:.2f}", SEM_COST)
                for other, score in sorted(graph.sem.get(relpath, {}).items())]
    return structural + semantic


def _walk_back(came_from: dict[str, tuple[str, str]], source: str,
               target: str) -> list[Hop]:
    hops: list[Hop] = []
    current = target
    while current != source:
        previous, via = came_from[current]
        hops.append({"file": current, "via": via})
        current = previous
    hops.append({"file": source, "via": ""})
    return hops[::-1]
