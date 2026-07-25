"""Sending one batch, and recovering when the endpoint says it was too big.

The split lives here rather than in the batcher because only the ENDPOINT knows
the real limit: the batcher estimates from a character ratio that measured 2.54
on one corpus and 1.47 on the next, and this reacts to the answer.
"""

from __future__ import annotations

import json
from typing import Protocol, Sequence

from .._arrays import Vector
from .._provider_errors import ProviderError
from ._batching import fit
from ._oversize import MAX_SPLITS, is_oversize
from ._retry import request_with_retry
from ._wire import decode_batch
from .http import RetryPolicy, Transport

__all__ = ["send_batch"]


class Wire(Protocol):
    """What sending needs from a configuration — nothing about caching."""

    endpoint: str
    model: str
    timeout: float

    def headers(self) -> dict[str, str]: ...


def send_batch(transport: Transport, config: Wire, policy: RetryPolicy,
               batch: Sequence[str], depth: int = 0) -> list[Vector]:
    """One request, splitting and retrying if the endpoint refuses its SIZE."""
    try:
        return _once(transport, config, policy, batch)
    except ProviderError as failure:
        if depth >= MAX_SPLITS or not is_oversize(str(failure)):
            raise
        if len(batch) == 1:
            # Nothing left to split: halve the text and try again. A file this
            # large is one nobody reads to the end either.
            half = max(1, len(batch[0]) // 2)
            return send_batch(transport, config, policy, [batch[0][:half]], depth + 1)
        middle = len(batch) // 2
        return [*send_batch(transport, config, policy, batch[:middle], depth + 1),
                *send_batch(transport, config, policy, batch[middle:], depth + 1)]


def _once(transport: Transport, config: Wire, policy: RetryPolicy,
          batch: Sequence[str]) -> list[Vector]:
    # Clipped HERE and nowhere else: the caller's text stays the key it reads
    # its vector back by, and only the wire sees the shortened one.
    body = json.dumps({"model": config.model,
                       "input": [fit(text) for text in batch],
                       "encoding_format": "base64"}).encode()
    payload = request_with_retry(transport, config.endpoint, body,
                                 headers=config.headers(),
                                 timeout=config.timeout, policy=policy)
    return decode_batch(payload, len(batch))
