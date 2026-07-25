"""The brief: the mental model for a question, as every surface sees it.

Prose comes from the model-authored cards (index time, oracle-gated). The
relations are NOT prose: `imports`/`imported_by` are rendered live from the
stored graph on every query, so they can never go stale and never hallucinate.
Which files appear — and their `score` — comes from the deterministic bundle,
so the brief inherits the engine's recall floors instead of ranking on its own.
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["Brief", "BriefFile", "BriefSymbol"]


class BriefSymbol(TypedDict):
    """One declared name — ground truth from the symbol table, never the model."""

    name: str
    kind: str
    line: int
    signature: str


class BriefFile(TypedDict):
    """One file of the mental model.

    `card` is the only model-written text in the payload. `degraded` marks
    skeleton-as-text: the oracle rejected the prose, or the bundle selected a
    file `study` never covered — worse prose either way, but it cannot lie.
    """

    file: str
    card: str
    degraded: bool
    score: float
    imports: list[str]          # rendered from edges at query time — always fresh
    imported_by: list[str]
    symbols: list[BriefSymbol]  # the interface, not the bodies


class Brief(TypedDict):
    """The whole answer: files in narrative order (graph-adjacent files read
    consecutively), each with its card, its live relations and its interface."""

    repo: str
    query: str
    files: list[BriefFile]
    considered: int             # files that competed in retrieval
    ms: int
