"""The dependency graph: build it, cluster it, walk it, draw it.

Hard rule #3 lives here: the graph supplies CANDIDATES and ANNOTATIONS, never
ranking. PageRank as a ranking signal was tried and dropped Acc@1 from 0.91 to
0.73 — nothing in this package returns a score, and nothing above it should
ask for one.
"""

from __future__ import annotations

from .build import RepoGraph, load_graph
from .clusters.communities import communities_of
from .clusters.gods import god_nodes
from .clusters.surprises import surprises_of
from .node import graph_node, neighbourhood
from .routes.paths import shortest_path
from .routes.route import graph_path
from .symbols.resolve import resolve_node
from .views import graph_map

__all__ = ["graph_map", "neighbourhood", "graph_node", "graph_path",
           "RepoGraph", "load_graph", "communities_of", "shortest_path",
           "god_nodes", "surprises_of", "resolve_node"]
