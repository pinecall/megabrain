"""The dependency graph, as the studio and the MCP client see it.

Every shape here is DISPLAY or NAVIGATION. Nothing in it is a score: the graph
supplies candidates and annotations, never ranking — that is hard rule #3, and
it was decided by experiment (PageRank as a ranking signal dropped Acc@1 from
0.91 to 0.73).
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["GraphLink", "GraphNode", "Community", "GraphMap", "GodNode",
           "Surprise"]


class GraphLink(TypedDict, total=False):
    """One dependency, undirected for drawing but labelled with its kinds."""

    source: str
    target: str
    kind: str                # "import", "call", "call/import", or "semantic"
    score: float             # semantic links only — how close, for the opacity


class GraphNode(TypedDict):
    file: str
    community: int
    degree: int              # neighbours in either direction — how connected
    in_degree: int           # who depends on THIS — how load-bearing


class Community(TypedDict):
    """A cluster of files that depend on each other more than on the rest.

    Numbered by size, 0 being the largest, so the numbering is stable across
    runs of the same repository instead of following iteration order.
    """

    id: int
    label: str               # what the code DOES, named once by a model
    size: int
    files: list[str]         # most connected first


class GodNode(TypedDict):
    """A file everything touches, reported with the split that diagnoses it.

    High `in` is load-bearing — everyone depends on it. High `out` is an
    orchestrator — it drives everything. High both is the file whose refactor
    nobody volunteers for.
    """

    file: str
    degree: int
    in_degree: int
    out_degree: int
    community: int


class Surprise(TypedDict):
    """Two files that do the same thing and have never met.

    The finding no ranking surfaces: similar enough to be twins, no edge
    between them, and in different clusters — which is what makes it worth
    saying instead of something the map already draws.
    """

    a: str
    b: str
    score: float


class GraphMap(TypedDict):
    """The whole repository at once."""

    repo: str
    files: int
    nodes: list[GraphNode]
    links: list[GraphLink]
    communities: list[Community]
    hubs: list[GraphNode]    # most depended upon — where a change lands hardest
    god_nodes: list[GodNode]
    surprises: list[Surprise]
    ms: int
