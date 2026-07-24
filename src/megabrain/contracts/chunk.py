"""Chunk-level payloads: what a located piece of code looks like on the wire.

Two distinctions here are load-bearing, and both come from checking real
payloads rather than reading the producing code:

`ChunkRef` vs `ChunkHit` — a tier-2 `best_chunk` carries NO score (the FILE was
ranked, not that span); a tier-1 chunk does (it was ranked among its siblings).
Modelling that as one optional field would let a scoreless span reach code that
sorts by score.

`ChunkHit` vs `PrunedChunk` — the flat pruned projection genuinely emits fewer
fields (no `part`, no `breadcrumb`). Two shapes, two types: an optional field
is a shape you failed to name.
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["Span", "ChunkRef", "ChunkHit", "PrunedChunk", "SymbolRef"]


class Span(TypedDict):
    """The minimum that makes something openable. A result the agent cannot
    open is not a result, so every payload naming a file carries its lines."""

    file: str
    start_line: int
    end_line: int


class ChunkRef(TypedDict):
    """A located chunk, unscored."""

    id: int
    file: str
    kind: str                # module | class | function | method | block | …
    name: str | None         # qualified: "Service.handle"
    part: str | None         # "2/5" when an oversized function was split
    start_line: int
    end_line: int
    text: str
    breadcrumb: str          # repo > path > Class > def method(sig)


class ChunkHit(ChunkRef):
    """A chunk that was ranked. `score` is FUSED relevance, not raw cosine."""

    score: float


class PrunedChunk(TypedDict):
    """The flat projection of `search --prune`: signal chunks, noise dropped."""

    id: int
    file: str
    start_line: int
    end_line: int
    kind: str
    name: str | None
    score: float
    text: str


class SymbolRef(TypedDict):
    """One entry of a file's outline. Display only — the graph never ranks."""

    name: str
    kind: str
    line: int
    end_line: int
    signature: str | None
    doc: str | None
