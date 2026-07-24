"""Model APIs. Split by layer, and the split is enforced.

`embeddings` is Layer 2: retrieval depends on it, and retrieval must stay
deterministic — an embedding is a pure function of its text, cached on disk.

`chat` is Layer 4: only `enrich/`, `ask/` and `forge/` may touch it. That is
hard rule #1, and tests/architecture is the fence.
"""

from __future__ import annotations

from ._retry import request_with_retry
from .http import Attempt, Response, RetryPolicy, Transport

__all__ = ["Response", "Transport", "Attempt", "RetryPolicy", "request_with_retry"]
