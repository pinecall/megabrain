"""Splitting texts into requests that the endpoint will actually accept.

By SIZE, not by count. A batch of ninety-six is fine for source files and
impossible for generated ones, and only their length knows which — measured in
the wild, one repository sent 164 614 tokens against a 120 000 limit and failed
the entire index on it.
"""

from __future__ import annotations

from typing import Iterator, Sequence

from ._budget import CHARS_PER_TOKEN, MAX_BATCH_TOKENS, estimate_tokens

__all__ = ["batches", "fit"]


def batches(texts: Sequence[str], size: int) -> Iterator[list[str]]:
    """Groups that respect BOTH the count and the token budget, in order.

    The groups hold the ORIGINAL texts, costed as they will be SENT — clipping
    happens at the request, never here. The text is the cache key and the key
    the caller reads its vector back by; substituting a clipped one loses the
    vector for the text that was actually asked about.

    Order is preserved because row *i* of a response is the vector for text *i*:
    regrouping that disturbed the sequence would attach each vector to a
    different text, and nothing downstream could detect it.
    """
    current: list[str] = []
    tokens = 0
    for text in texts:
        cost = estimate_tokens(fit(text))
        if current and (len(current) >= size or tokens + cost > MAX_BATCH_TOKENS):
            yield current
            current, tokens = [], 0
        current.append(text)
        tokens += cost
    if current:
        yield current


def fit(text: str) -> str:
    """One text, clipped to the budget it must fit inside on its own.

    A single generated file can exceed the limit by itself. Refusing it fails
    the whole repository over one file; embedding its beginning indexes that
    file a little worse and indexes everything else perfectly — and a file that
    large is one nobody reads to the end either.
    """
    limit = int(MAX_BATCH_TOKENS * CHARS_PER_TOKEN)   # the budget, in characters
    return text if len(text) <= limit else text[:limit]
