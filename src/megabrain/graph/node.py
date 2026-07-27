"""One file, from the graph's point of view.

`imported_by` is the half a reader cannot get by opening the file: what needs
this is invisible from inside it, and it is the thing that decides whether a
change is safe. The semantic ties are the other half — the files that do the
same job and would have to change with it, edge or no edge.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..contracts import Neighbourhood, NodeEdge, NodeView, SemanticTie
from ..storage import Store
from ..storage.locate import resolve_root
from .build import load_graph
from .clusters.communities import communities_of
from .clusters.labels import label_communities
from .symbols.resolve import resolve_node

__all__ = ["graph_node", "neighbourhood"]


def graph_node(start: Path | str, term: str, *, label: bool = False,
               embedder: object = None) -> NodeView:
    """The full node view, for a TERM — a path, a filename, or a description."""
    started = time.perf_counter()
    root = resolve_root(start)
    graph = load_graph(str(root))
    with Store(root) as store:
        relpath = resolve_node(store, graph.files, term, embedder)
        if relpath is None:
            raise FileNotFoundError(f"no file in this index matches {term!r}")
        edges = store.graph.all_edges()
        symbols = store.symbols.read_for(relpath)
    labels = communities_of(graph)
    names = (label_communities(str(root), graph, labels) if label else {})
    community = labels[relpath]
    return NodeView(
        repo=root.name, file=relpath, resolved_from=term,
        community=community,
        community_label=names.get(community, f"Community {community}"),
        degree=graph.degree(relpath),
        imports=_edges(edges, relpath, outgoing=True),
        imported_by=_edges(edges, relpath, outgoing=False),
        semantic=sorted((SemanticTie(file=other, score=round(score, 3))
                         for other, score in graph.sem.get(relpath, {}).items()),
                        key=lambda tie: (-tie["score"], tie["file"])),
        symbols=symbols, ms=int((time.perf_counter() - started) * 1000))


def neighbourhood(start: Path | str, relpath: str) -> Neighbourhood:
    """The small view: one file's immediate dependencies, both directions.

    Kept separate from `graph_node` on purpose — the CLI and the MCP tool want
    two lists of paths, and paying for symbols, chunks and a community label to
    print them would be a worse answer arrived at more slowly.
    """
    started = time.perf_counter()
    graph = load_graph(str(resolve_root(start)))
    if relpath not in graph.near:
        raise FileNotFoundError(f"{relpath} is not in this index")
    return Neighbourhood(
        file=relpath, community=communities_of(graph)[relpath],
        imports=sorted(graph.out.get(relpath, set())),
        imported_by=sorted(graph.into.get(relpath, set())),
        ms=int((time.perf_counter() - started) * 1000))


def _edges(edges: list[tuple[str, str, str]], relpath: str,
           *, outgoing: bool) -> list[NodeEdge]:
    """Kept per KIND rather than merged: "imports it" and "calls it" are
    different facts about the same pair, and the node view is where somebody is
    looking for exactly that difference."""
    found: list[NodeEdge] = []
    for source, target, kind in edges:
        near, far = (source, target) if outgoing else (target, source)
        if near == relpath:
            found.append(NodeEdge(file=far, kind=kind))
    return sorted(found, key=lambda edge: (edge["file"], edge["kind"]))
