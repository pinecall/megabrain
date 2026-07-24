"""How two files are connected.

The question a dependency graph answers that nothing else can: not "are these
related" — search answers that — but "through WHAT", which is the chain
somebody has to read before changing either end.
"""

from __future__ import annotations

from collections import deque

from .build import RepoGraph

__all__ = ["shortest_path"]


def shortest_path(graph: RepoGraph, source: str, target: str) -> list[str]:
    """The fewest hops from `source` to `target`, or [] if unconnected.

    Undirected: "how are these two connected" is not a question about
    direction, and answering it directionally hides the common case where two
    files meet at a third that imports them both.

    Breadth-first, so the FIRST route found is the shortest — a depth-first
    walk returns whichever branch it happened to descend, which on a real
    repository is a plausible-looking tour of twelve files.
    """
    if source not in graph.near or target not in graph.near:
        return []
    if source == target:
        return [source]
    came_from: dict[str, str] = {source: source}
    queue = deque([source])
    while queue:
        current = queue.popleft()
        for neighbour in sorted(graph.near.get(current, {})):
            if neighbour in came_from:
                continue
            came_from[neighbour] = current
            if neighbour == target:
                return _walk_back(came_from, source, target)
            queue.append(neighbour)
    return []


def _walk_back(came_from: dict[str, str], source: str, target: str) -> list[str]:
    hops = [target]
    while hops[-1] != source:
        hops.append(came_from[hops[-1]])
    return hops[::-1]
