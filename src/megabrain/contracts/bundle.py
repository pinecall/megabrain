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

from .chunk import ChunkHit, ChunkRef, Span, SymbolRef

__all__ = ["Bundle", "Tier1File", "Tier2File", "FlowHit", "AnchorHit"]


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


class FlowHit(TypedDict):
    """A cached ask synthesis that matched. `sha` pins the code it described,
    so a flow dies with the source it cited."""

    question: str
    text: str
    files: list[str]
    sha: dict[str, str]
    score: float                  # question+prose similarity (ATTACH lane)
    qscore: float                 # question-only similarity (SERVE lane)


class AnchorHit(Span):
    """A chunk the lexical anchor floor pulled in: a rare identifier the query
    quoted lives verbatim in its text. A pure addition — never displaces."""

    terms: list[str]


class Bundle(TypedDict):
    """What `search` returns: CORE with code, RELATED as a map, plus the two
    recall lanes (flows, anchors) that only ever ADD."""

    query: str
    repo: str
    tier1: list[Tier1File]
    tier2: list[Tier2File]
    flows: list[FlowHit]
    anchors: list[AnchorHit]
    ms: int
