"""The whole-repository map, as a contract.

Assembly only: every number here was computed by `build`, `communities`,
`gods`, `surprises` or `labels`. Nothing in this module decides anything, which
is what keeps the "graph never ranks" rule checkable by reading one file.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..contracts import Community, GraphLink, GraphMap, GraphNode
from ..storage.locate import resolve_root
from .build import RepoGraph, load_graph
from .communities import communities_of
from .gods import god_nodes
from .labels import label_communities
from .surprises import surprises_of

__all__ = ["graph_map", "HUBS"]

HUBS = 10


def graph_map(start: Path | str, *, label: bool = True) -> GraphMap:
    """The whole repository: nodes, links, clusters, cores and surprises.

    `label` is the only optional part, and the only one that can touch a model.
    Off, the map is pure local computation — which is what the CLI and every
    test use.
    """
    started = time.perf_counter()
    root = resolve_root(start)
    graph = load_graph(str(root))
    labels = communities_of(graph)
    names = (label_communities(str(root), graph, labels) if label
             else {cid: f"Community {cid}" for cid in set(labels.values())})
    nodes = [_node(graph, labels, relpath) for relpath in graph.files]
    return GraphMap(
        repo=root.name, files=len(graph.files), nodes=nodes,
        links=_links(graph), communities=_communities(graph, labels, names),
        hubs=sorted(nodes, key=lambda n: (-n["in_degree"], n["file"]))[:HUBS],
        god_nodes=god_nodes(graph, labels), surprises=surprises_of(graph, labels),
        ms=int((time.perf_counter() - started) * 1000))


def _node(graph: RepoGraph, labels: dict[str, int], relpath: str) -> GraphNode:
    return GraphNode(file=relpath, community=labels[relpath],
                     degree=graph.degree(relpath), in_degree=graph.in_degree(relpath))


def _links(graph: RepoGraph) -> list[GraphLink]:
    """Each pair ONCE per lane, with its kinds joined.

    A file that both imports and calls another is one dependency; drawn twice it
    reads as two, and a map's whole job is to be read at a glance. The semantic
    lane is a SEPARATE link carrying its score, never merged into a structural
    kind — the reader would go looking for a call that does not exist.
    """
    links: list[GraphLink] = []
    seen: set[tuple[str, str]] = set()
    for source in graph.files:
        for target, kinds in sorted(graph.near.get(source, {}).items()):
            pair = (min(source, target), max(source, target))
            if pair not in seen:
                seen.add(pair)
                links.append(GraphLink(source=pair[0], target=pair[1],
                                       kind="/".join(sorted(kinds))))
    return links + _semantic_links(graph, seen)


def _semantic_links(graph: RepoGraph, structural: set[tuple[str, str]]) -> list[GraphLink]:
    """Only where structure has nothing to say. A pair that already imports is
    not made more connected by also reading alike, and drawing both edges
    doubles the clutter for no added fact."""
    links: list[GraphLink] = []
    seen: set[tuple[str, str]] = set()
    for source in graph.files:
        for target, score in sorted(graph.sem.get(source, {}).items()):
            pair = (min(source, target), max(source, target))
            if pair in seen or pair in structural:
                continue
            seen.add(pair)
            links.append(GraphLink(source=pair[0], target=pair[1],
                                   kind="semantic", score=round(score, 3)))
    return links


def _communities(graph: RepoGraph, labels: dict[str, int],
                 names: dict[int, str]) -> list[Community]:
    grouped: dict[int, list[str]] = {}
    for relpath, label in labels.items():
        grouped.setdefault(label, []).append(relpath)
    return [Community(id=label, label=names.get(label, f"Community {label}"),
                      size=len(files),
                      files=sorted(files, key=lambda f: (-graph.degree(f), f)))
            for label, files in sorted(grouped.items())]
