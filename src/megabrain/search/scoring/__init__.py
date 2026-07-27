"""Chunk scoring — deterministic, embedding-only, no language model."""

from __future__ import annotations

from .lane import Lane
from .lanes import LANES
from .pipeline import score_chunks

__all__ = ["score_chunks", "Lane", "LANES"]
