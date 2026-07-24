"""The dependency graph: build it, cluster it, walk it, draw it.

Hard rule #3 lives here: the graph supplies CANDIDATES and ANNOTATIONS, never
ranking. PageRank as a ranking signal was tried and dropped Acc@1 from 0.91 to
0.73 — nothing in this package returns a score, and nothing above it should
ask for one.
"""

from __future__ import annotations

from .build import RepoGraph, load_graph
from .communities import communities_of
from .paths import shortest_path
from .views import graph_map, graph_path, neighbourhood

__all__ = ["graph_map", "neighbourhood", "graph_path",
           "RepoGraph", "load_graph", "communities_of", "shortest_path"]
