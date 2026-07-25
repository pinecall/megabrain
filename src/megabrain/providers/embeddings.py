"""Text -> vectors, through any OpenAI-compatible `/embeddings` endpoint.

Layer 2: retrieval depends on this, so it holds no LLM and makes no decisions —
an embedding is a pure function of its text, which is what makes caching it on
disk sound rather than a guess.
"""

from __future__ import annotations

import json
from typing import Callable, Sequence

from .._arrays import Vector
from .._types import NotGiven, is_given, not_given
from ._batching import batches, fit
from ._config import DEFAULT_BATCH, EmbedConfig
from ._retry import request_with_retry
from ._wire import decode_batch
from .cache import EmbedCache, remember, split_cached
from .http import RetryPolicy, Transport

__all__ = ["Embedder"]

ProgressFn = Callable[[int, int], None]


class Embedder:
    def __init__(self, *, transport: Transport | None = None,
                 api_key: str | None | NotGiven = not_given,
                 model: str | None = None, base_url: str | None = None,
                 batch_size: int = DEFAULT_BATCH, timeout: float = 120.0,
                 policy: RetryPolicy | None = None,
                 cache: EmbedCache | None | NotGiven = not_given) -> None:
        self.config = EmbedConfig.resolve(api_key=api_key, model=model, base_url=base_url,
                                          batch_size=batch_size, timeout=timeout)
        self.policy = policy or RetryPolicy()
        # Omitted enables the shared on-disk cache; an explicit None turns it
        # off, which is what a test measuring real calls needs.
        self.cache = EmbedCache() if not is_given(cache) else cache
        self.tokens = 0
        self._transport = transport

    @property
    def model(self) -> str:
        return self.config.model

    def embed(self, texts: Sequence[str], *, on_batch: ProgressFn | None = None) -> list[Vector]:
        """Embed every text, in order. Row *i* is the vector for `texts[i]`.

        Order is the contract. A reordering never raises — it just attaches
        each chunk's vector to a different chunk, and the index is then wrong
        in a way nothing downstream can detect.
        """
        if not texts:
            return []
        cached, missing = split_cached(self.cache, self.config.model, texts)
        if missing:
            self.config.require_key()
        for batch in batches(missing, self.config.batch_size):
            for text, vector in zip(batch, self._embed_one(batch)):
                cached[text] = vector
                remember(self.cache, self.config.model, text, vector)
            # Reported per batch, not once at the end: indexing a large
            # repository is a long silence otherwise, and progress counts the
            # CALLER's texts — a cache hit is done work, not skipped work.
            if on_batch is not None:
                on_batch(sum(1 for t in texts if t in cached), len(texts))
        if on_batch is not None and not missing:
            on_batch(len(texts), len(texts))
        return [cached[t] for t in texts]

    def _embed_one(self, batch: Sequence[str]) -> list[Vector]:
        # Clipped HERE and nowhere else: the caller's text stays the key it
        # reads its vector back by, and only the wire sees the shortened one.
        body = json.dumps({"model": self.config.model,
                           "input": [fit(text) for text in batch],
                           "encoding_format": "base64"}).encode()
        payload = request_with_retry(
            self._require_transport(), self.config.endpoint, body,
            headers=self.config.headers(),
            timeout=self.config.timeout, policy=self.policy)
        self.tokens += sum(len(t) for t in batch) // 4    # rough, for reporting only
        return decode_batch(payload, len(batch))

    def _require_transport(self) -> Transport:
        """Imported on first use, not at module load — nothing that merely
        imports the engine should pay for urllib."""
        if self._transport is None:
            from ._urllib import UrllibTransport
            self._transport = UrllibTransport()
        return self._transport

