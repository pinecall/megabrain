"""The flat projection of the bundle: `search --prune`.

Same selection, different shape — signal chunks ranked flat with the noise
dropped. It is a PROJECTION, not a second retrieval: whatever the bundle chose
is what this can show.

The optional tail (`setaside`, `related_docs`, `related_tests`) appears only
when the corresponding lane ran. See bundle.py for why optionality is spelled
with a `total=False` split and never with `NotRequired`.
"""

from __future__ import annotations

from typing import TypedDict

from .chunk import PrunedChunk, Span

__all__ = ["PruneResult", "NoiseSpan", "RelatedDoc", "RelatedTest"]


class NoiseSpan(Span):
    """A span the pruner dropped. Reported so a caller can audit what was
    considered and rejected — pruning that hides its own losses is
    unauditable, and an agent that cannot see the near-misses cannot tell a
    confident answer from a lucky one."""

    score: float


class RelatedDoc(Span, total=False):
    """A doc span the same query matched. Carries the SPAN, not just the file:
    a bare filename makes the agent read the whole document (field run: 426
    lines of a guide fetched to reach an ~80-line section)."""

    changelog: bool               # a fixed edit target, pinned deterministically


class RelatedTest(TypedDict):
    """A test file that NAMES the surface's symbols — the tests that PIN the
    mechanism. Deterministic and phrasing-stable: a literal scan, no LLM."""

    file: str
    start_line: int
    n: int                        # how many surface symbols this file names


class _PruneRequired(TypedDict):
    query: str
    repo: str
    chunks: list[PrunedChunk]
    kept: int
    pruned: int
    scanned: int
    noise_map: list[NoiseSpan]
    ms: int


class PruneResult(_PruneRequired, total=False):
    """What `search --prune` returns."""

    setaside: list[PrunedChunk]   # near-ties the judge demoted but kept reachable
    related_docs: list[RelatedDoc]
    related_tests: list[RelatedTest]
