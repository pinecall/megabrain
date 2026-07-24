"""The three graph views, as contracts.

Assembly only: every number here was computed by `build`, `communities` or
`paths`. Nothing in this module decides anything, which is what keeps the
"graph never ranks" rule checkable by reading one file.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..contracts import Community, GraphLink, GraphMap, GraphNode, GraphPath, Neighbourhood
from ..usecases import resolve_root
from .build import RepoGraph, load_graph
from .communities import communities_of
from .paths import shortest_path

__all__ = ["graph_map", "neighbourhood", "graph_path", "HUBS"]

HUBS = 10


def graph_map(start: Path | str) -> GraphMap:
    """The whole repository: nodes, links, clusters, and what depends on what."""
    started = time.perf_counter()
    root = resolve_root(start)
    graph = load_graph(str(root))
    labels = communities_of(graph)
    nodes = [_node(graph, labels, relpath) for relpath in graph.files]
    return GraphMap(
        repo=root.name, files=len(graph.files), nodes=nodes,
        links=_links(graph), communities=_communities(graph, labels),
        hubs=sorted(nodes, key=lambda n: (-n["in_degree"], n["file"]))[:HUBS],
        ms=int((time.perf_counter() - started) * 1000))


def neighbourhood(start: Path | str, relpath: str) -> Neighbourhood:
    started = time.perf_counter()
    graph = load_graph(str(resolve_root(start)))
    if relpath not in graph.near:
        raise FileNotFoundError(f"{relpath} is not in this index")
    return Neighbourhood(
        file=relpath, community=communities_of(graph)[relpath],
        imports=sorted(graph.out.get(relpath, set())),
        imported_by=sorted(graph.into.get(relpath, set())),
        ms=int((time.perf_counter() - started) * 1000))


def graph_path(start: Path | str, source: str, target: str) -> GraphPath:
    started = time.perf_counter()
    graph = load_graph(str(resolve_root(start)))
    hops = shortest_path(graph, source, target)
    return GraphPath(source=source, target=target, hops=hops, found=bool(hops),
                     ms=int((time.perf_counter() - started) * 1000))


def _node(graph: RepoGraph, labels: dict[str, int], relpath: str) -> GraphNode:
    return GraphNode(file=relpath, community=labels[relpath],
                     degree=graph.degree(relpath), in_degree=graph.in_degree(relpath))


def _links(graph: RepoGraph) -> list[GraphLink]:
    """Each pair ONCE, with its kinds joined.

    A file that both imports and calls another is one dependency; drawn twice
    it reads as two, and a map's whole job is to be read at a glance.
    """
    seen: set[tuple[str, str]] = set()
    links: list[GraphLink] = []
    for source in graph.files:
        for target, kinds in sorted(graph.near.get(source, {}).items()):
            pair = (min(source, target), max(source, target))
            if pair in seen:
                continue
            seen.add(pair)
            links.append(GraphLink(source=pair[0], target=pair[1],
                                   kind="/".join(sorted(kinds))))
    return links


def _communities(graph: RepoGraph, labels: dict[str, int]) -> list[Community]:
    grouped: dict[int, list[str]] = {}
    for relpath, label in labels.items():
        grouped.setdefault(label, []).append(relpath)
    return [Community(id=label, size=len(files),
                      files=sorted(files, key=lambda f: (-graph.degree(f), f)))
            for label, files in sorted(grouped.items())]
