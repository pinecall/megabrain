"""A built graph, kept for as long as the index it came from.

`load_graph` is milliseconds of adjacency — and, since the semantic lane, also
every skeleton cosine. Rebuilding all of that per request made the studio's
Graph tab pay the whole bill on every click. The key is the index file's stat
rather than a content fingerprint: a fingerprint needs the graph to compute,
which is exactly the work the cache exists to skip. A re-index rewrites the
file, the stat moves, the entry dies.
"""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from ..storage.locate import INDEX_FILE
from .build import RepoGraph, load_graph

__all__ = ["warm_graph"]

_CACHE: dict[str, tuple[tuple[int, int], RepoGraph]] = {}
_LOCK = Lock()


def warm_graph(root: str) -> RepoGraph:
    """The repository's graph — rebuilt only when the index file changed.

    `RepoGraph` is frozen and nothing mutates it after build, so one instance
    is safe to hand to every server thread at once. A missing index falls
    through to `load_graph`, whose error names the problem.
    """
    stamp = _stamp(root)
    if stamp is not None:
        with _LOCK:
            held = _CACHE.get(root)
            if held is not None and held[0] == stamp:
                return held[1]
    graph = load_graph(root)
    if stamp is not None:
        with _LOCK:
            _CACHE[root] = (stamp, graph)
    return graph


def _stamp(root: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(Path(root) / INDEX_FILE)
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size
