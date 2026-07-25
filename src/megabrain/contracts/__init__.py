"""Layer 1 — every payload that crosses a boundary, defined once.

ZERO logic lives here: only types. `retrieval` produces them, `render` and
`ask` consume them, the CLI/MCP/HTTP transports serialize them, and the studio
mirrors them. One definition, six readers.

This package imports nothing but L0, so it can never introduce a cycle — which
is what lets every layer above depend on it freely.
"""

from __future__ import annotations

from .bundle import AnchorHit, Bundle, FlowHit, Tier1File, Tier2File
from .chunk import ChunkHit, ChunkRef, PrunedChunk, Span, SymbolRef
from .file import FileView
from .graph import Community, GodNode, GraphLink, GraphMap, GraphNode, Surprise
from .node import Neighbourhood, NodeEdge, NodeView, SemanticTie
from .prune import NoiseSpan, PruneResult, RelatedDoc, RelatedTest
from .repo import RepoEntry
from .route import CodeSnip, GraphPath, Hop, HopCode
from .scan import ScanReport, SkippedFile

__all__ = [
    # chunk level
    "Span", "ChunkRef", "ChunkHit", "PrunedChunk", "SymbolRef",
    # the bundle
    "Bundle", "Tier1File", "Tier2File", "FlowHit", "AnchorHit",
    # one file, expanded
    "FileView",
    # the machine's indexed repositories
    "RepoEntry",
    # the pre-index census
    "ScanReport", "SkippedFile",
    # the dependency graph
    "GraphMap", "GraphNode", "GraphLink", "Community", "Neighbourhood", "GraphPath",
    "GodNode", "Surprise", "Hop", "HopCode", "CodeSnip",
    "NodeView", "NodeEdge", "SemanticTie",
    # the flat projection
    "PruneResult", "NoiseSpan", "RelatedDoc", "RelatedTest",
]
