"""One file, as the graph sees it.

The node view is the studio's detail panel: both edge directions kept per KIND,
the semantic twins, and the file's own symbols. `Neighbourhood` is the small
version for the CLI and MCP — two lists of paths, no model call, no symbols.
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["NodeEdge", "SemanticTie", "NodeView", "Neighbourhood"]


class NodeEdge(TypedDict):
    file: str
    kind: str


class SemanticTie(TypedDict):
    file: str
    score: float


class NodeView(TypedDict):
    """One file: its community, both edge directions, its twins, its symbols."""

    repo: str
    file: str
    resolved_from: str
    community: int
    community_label: str
    degree: int
    imports: list[NodeEdge]
    imported_by: list[NodeEdge]
    semantic: list[SemanticTie]
    symbols: list[dict[str, object]]
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
