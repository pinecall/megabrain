"""Layer 2 — the index on disk. The only package that writes SQL."""

from __future__ import annotations

from .model import ChunkMeta
from .store import Store

__all__ = ["Store", "ChunkMeta"]
