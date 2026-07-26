"""Text -> vectors, through any OpenAI-compatible `/embeddings` endpoint.

Layer 2: retrieval depends on this, so it stays deterministic — an embedding is a
pure function of its text, cached on disk.

`providers.embeddings` is the path every caller already uses
(`from ..providers.embeddings import Embedder`, six sites in `src/` and as many
in tests), so `Embedder` is re-exported here and the split into a codec, a
batching policy and a cache is invisible from outside.
"""

from __future__ import annotations

from .cache import EmbedCache
from .client import Embedder

__all__ = ["Embedder", "EmbedCache"]
