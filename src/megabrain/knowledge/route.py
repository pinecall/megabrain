"""How two files are connected, told properly.

Three steps, each in its own module: resolve both ends from whatever the user
typed, find the cheapest informative route, then annotate it with the symbols
and code that make it evidence rather than a claim.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..contracts import GraphPath, Hop
from ..storage import Store
from ..storage.locate import resolve_root
from .build import load_graph
from .paths import shortest_path
from .resolve import resolve_node
from .story import tell

__all__ = ["graph_path"]


def graph_path(start: Path | str, source: str, target: str,
               embedder: object = None) -> GraphPath:
    started = time.perf_counter()
    root = resolve_root(start)
    graph = load_graph(str(root))
    with Store(root) as store:
        one = resolve_node(store, graph.files, source, embedder)
        two = resolve_node(store, graph.files, target, embedder)
        hops: list[Hop] = shortest_path(graph, one, two) if one and two else []  # type: ignore[arg-type]
        told = tell(store, root, hops)
    walked: list[Hop] = told["hops"]  # type: ignore[assignment]
    return GraphPath(
        source=walked[0]["file"] if walked else (one or source),
        target=walked[-1]["file"] if walked else (two or target),
        hops=walked, found=bool(walked), flipped=bool(told["flipped"]),
        chain=bool(told["chain"]), meet=told["meet"],  # type: ignore[typeddict-item]
        meet_kind=told["meet_kind"],  # type: ignore[typeddict-item]
        ms=int((time.perf_counter() - started) * 1000))
