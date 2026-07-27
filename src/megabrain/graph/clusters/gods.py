"""God nodes: the files everything touches.

Ranked by TOTAL degree but reported with the in/out split, because the split
is the diagnosis: high-in is load-bearing (everyone depends on it), high-out
is an orchestrator (it drives everything), and high-both is the file whose
refactor nobody volunteers for.
"""

from __future__ import annotations

from ...contracts import GodNode
from ..build import RepoGraph

__all__ = ["god_nodes", "GODS_TOP"]

GODS_TOP = 10


def god_nodes(graph: RepoGraph, communities: dict[str, int]) -> list[GodNode]:
    ranked = sorted(graph.files, key=lambda f: (-graph.degree(f), f))
    return [GodNode(file=relpath, degree=graph.degree(relpath),
                    in_degree=graph.in_degree(relpath),
                    out_degree=len(graph.out.get(relpath, set())),
                    community=communities.get(relpath, 0))
            for relpath in ranked[:GODS_TOP] if graph.degree(relpath) > 0]
