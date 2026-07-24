"""The dependency graph, as the studio and the MCP client see it.

Every shape here is DISPLAY or NAVIGATION. Nothing in it is a score: the graph
supplies candidates and annotations, never ranking — that is hard rule #3, and
it was decided by experiment (PageRank as a ranking signal dropped Acc@1 from
0.91 to 0.73).
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["GraphLink", "GraphNode", "Community", "GraphMap",
           "Neighbourhood", "GraphPath"]


class GraphLink(TypedDict):
    """One dependency, undirected for drawing but labelled with its kinds."""

    source: str
    target: str
    kind: str                # "import", "call", or "call/import" when both


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
    size: int
    files: list[str]         # most connected first


class GraphMap(TypedDict):
    """The whole repository at once."""

    repo: str
    files: int
    nodes: list[GraphNode]
    links: list[GraphLink]
    communities: list[Community]
    hubs: list[GraphNode]    # most depended upon — where a change lands hardest
    ms: int


class Neighbourhood(TypedDict):
    """One file and its immediate dependencies, both directions.

    `imported_by` is half the value: "who calls this" is what turns a hit into
    an understanding of why the code exists.
    """

    file: str
    community: int
    imports: list[str]
    imported_by: list[str]
    ms: int


class GraphPath(TypedDict):
    """How two files are connected, if they are."""

    source: str
    target: str
    hops: list[str]          # source … target, empty when unreachable
    found: bool
    ms: int
