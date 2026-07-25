"""Recovering from "your batch is too big".

The estimate that decides batch size cannot be right for every repository —
measured, the same content type came out at 2.54 characters per token and then
at 1.47. So the estimate is a performance heuristic, and THIS is the
correctness guarantee: a refusal splits the batch and retries, and a single text
that cannot fit alone is clipped until it does.

Only SIZE refusals are retried. Splitting a credential error just fails it twice
as often and buries the message that named the problem.
"""

from __future__ import annotations

import re

__all__ = ["is_oversize", "MAX_SPLITS"]

# Bounded: an unbounded split is an infinite loop wearing a recovery costume.
# Five halvings take a 96-text batch to 3, which is past any real limit.
MAX_SPLITS = 5

_OVERSIZE = re.compile(
    r"exceeds maximum|too many tokens|maximum context length|"
    r"reduce the length|input is too large|max_tokens_per_request",
    re.IGNORECASE)


def is_oversize(message: str) -> bool:
    """Whether a provider's refusal was about SIZE.

    Matched on the message because that is all the wire carries: the gateway
    that provoked this returns HTTP 200 with the refusal in the body, so there
    is no status to classify and no error code that means "too big" across
    providers.
    """
    return bool(_OVERSIZE.search(message))
