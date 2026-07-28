"""One place that turns a Strategy into the Chunker that runs it.

The optional `budget` attribute is the extension point specialization needs:
a strategy that wants tighter chunks says so as data, and the pipeline honours
it here — the alternative was a second Chunker construction site per caller,
each with its own idea of the default.
"""

from __future__ import annotations

from ..chunkers import DEFAULT_BUDGET, Chunker
from .strategies import Strategy

__all__ = ["chunker_for"]


def chunker_for(strategy: Strategy, *, repo: str = "") -> Chunker:
    budget = getattr(strategy, "budget", DEFAULT_BUDGET)
    return Chunker(strategy.parse, repo=repo, budget=int(budget))
