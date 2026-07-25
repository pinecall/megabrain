"""The retrieval bundle — the engine's central artifact.

Six readers consume this — `render`, `ask`, the CLI, MCP, HTTP and the studio —
so it is declared once here rather than rediscovered by reading the producer.

TypedDict on purpose, not a dataclass and not pydantic: at runtime these ARE
dicts, so a consumer writes `res["chunks"]`, the wire format is the same object
serialised, and the engine gains no dependency.

Every field is verified against real captured payloads (tests/fixtures/parity/)
rather than against what the producing code looks like it returns — the two
disagree more often than anyone expects.

⚠️ Optionality uses the `total=False` SPLIT, never `NotRequired`. Under
`from __future__ import annotations` every annotation is a string, so TypedDict
cannot see a `NotRequired[...]` marker at class-creation time: `__optional_keys__`
comes back EMPTY and every field silently reads as required to anything that
introspects the class (the shape checker, an MCP schema generator, a runtime
validator). Totality is class-level, so the split is immune.
tests/contracts/test_optionality.py pins this.
"""

from __future__ import annotations

from typing import TypedDict

from .chunk import ChunkHit, ChunkRef, SymbolRef
from .lanes import AnchorHit, FlowHit

__all__ = ["JudgeVerdict", "Bundle", "Tier1File", "Tier2File",
           "FlowHit", "AnchorHit"]


class Tier1File(TypedDict):
    """CORE: the full code of the matching chunks + an outline for the rest."""

    file: str
    score: float
    chunks: list[ChunkHit]
    symbols: list[SymbolRef]
    neighbors: list[str]


class _Tier2Required(TypedDict):
    file: str
    score: float
    via_graph: bool               # reached through an import/call edge
    matched: list[str]
    doc: str | None
    best_chunk: ChunkRef | None   # unscored: the FILE was ranked, not this span
    symbols: list[SymbolRef]


class Tier2File(_Tier2Required, total=False):
    """RELATED: a map, not bodies — file, best span, symbols. ~60% fewer tokens."""

    via_flow: bool                # surfaced by the cached-walkthrough lane


class JudgeVerdict(TypedDict):
    """What the judge lane decided about the RELATED tier."""

    kept: int
    of: int


class Bundle(TypedDict):
    """What `search` returns: CORE with code, RELATED as a map, plus the two
    recall lanes (flows, anchors) that only ever ADD."""

    query: str
    repo: str
    tier1: list[Tier1File]
    tier2: list[Tier2File]
    flows: list[FlowHit]
    anchors: list[AnchorHit]
    judge: "JudgeVerdict | None"
    """The judge lane's verdict, when it ran: how many RELATED files it kept.

    None and kept-0 are DIFFERENT answers. None means the lane never spoke —
    off, no provider, failed open. kept-0 means it spoke and rejected every
    candidate: the list below merely shares vocabulary with the task. That
    verdict was being discarded (an empty reorder changes nothing), and it is
    exactly the signal the evidence band cannot see — the band reads the top-1
    cosine, which is often RIGHT while the rest of the list is noise."""
    evidence: str
    """"strong" | "weak" | "none" — how much the index actually offered.

    The fused scores cannot say this: their scale is offset so a zero cosine
    displays as 0.75, and an off-topic query's CORE looks like a hit. The band
    comes from the RAW top cosine, calibrated in `scoring/evidence.py`, and it
    is what lets a surface stop writing confident prose over nothing."""
    top_cosine: float
    expanded: list[str]
    """Terms the expander lane named — empty when it did not run, or found the
    search already complete. The reader is owed it: a file that arrived this
    way did not answer the question as asked, it answered a term a model
    proposed after seeing what the question missed."""
    ms: int
