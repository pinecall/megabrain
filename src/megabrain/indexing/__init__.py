"""Repository -> index. Walk, chunk, embed, store.

Layer 3, and deterministic: nothing here calls a language model. The only
network is the embedding endpoint, and an embedding is a pure function of its
text.
"""

from __future__ import annotations

from .discover import discover
from .indexer import index_repo
from .strategies import EDGE_SCHEMA, Registry, Strategy

__all__ = ["index_repo", "discover", "Strategy", "Registry", "EDGE_SCHEMA"]
