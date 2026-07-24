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
from .prune import NoiseSpan, PruneResult, RelatedDoc, RelatedTest

__all__ = [
    # chunk level
    "Span", "ChunkRef", "ChunkHit", "PrunedChunk", "SymbolRef",
    # the bundle
    "Bundle", "Tier1File", "Tier2File", "FlowHit", "AnchorHit",
    # one file, expanded
    "FileView",
    # the flat projection
    "PruneResult", "NoiseSpan", "RelatedDoc", "RelatedTest",
]
