"""The phases of one index pass, in the order that makes the network cost once.

    plan      chunk what changed          pure CPU, no network
    embed     one request for the lot     the only expensive step
    write     one transaction             reached only after every vector is back
    resymbol  re-extract symbols          free: a parse, no embedding

The ordering is the design, not an accident: a network failure aborts BEFORE any
row is touched, so the previous index survives intact rather than half-replaced.
Kept as private names inside a package the caller never imports directly —
`indexer.py` is the only orchestrator.
"""

from __future__ import annotations

__all__: list[str] = []
