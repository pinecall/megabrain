"""The two relations a node view carries beyond its import graph.

Kept apart from the edge listing because they answer different questions. A
PIN is a test fixing this file\'s behaviour — "what turns red", not "what
breaks", and counting it as a dependant inflated fastapi\'s `routing.py` to 96.
A TWIN is a file doing the same job with no edge either way, which is the row
a port reads to find the duplicate it was about to write twice.
"""

from __future__ import annotations

from ..contracts import SemanticTie

__all__ = ["pinned_by", "twins_of", "MAX_PINS"]

MAX_PINS = 6
"""Pin rows NAMED. MEASURED: splitting pins out of the dependants made the
render longer, not shorter — 44 test paths where the actionable fact is the
number. Whoever changes the file runs the suite; they do not read the roster."""


def pinned_by(files: set[str]) -> list[str]:
    """Tests that pin this file and never import it — nothing when there are
    none, because a section promising a relation that does not exist is noise
    in every render that does not have it."""
    if not files:
        return []
    shown = sorted(files)[:MAX_PINS]
    tail = ([f"  … {len(files) - MAX_PINS} more — run the suite, not this list"]
            if len(files) > MAX_PINS else [])
    plural = "" if len(files) == 1 else "s"
    return [f"\npinned by {len(files)} test{plural}:",
            *(f"  ⊨ {path}" for path in shown), *tail]


def twins_of(ties: list[SemanticTie]) -> list[str]:
    """Semantically the same job, structurally strangers. Always printed, even
    empty: "no twin" is a finding — it says this file is not a duplicate."""
    if not ties:
        return ["\nsemantic twins (no edge between them): none"]
    return [f"\nsemantic twins (no edge between them) ({len(ties)}):",
            *(f"  ≈ {tie['file']}  {tie['score']:.2f}" for tie in ties)]
