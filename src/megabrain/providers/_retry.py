"""The retry loop itself: send, classify, wait, repeat.

Kept apart from the policy so the decision ("should this be retried, and for
how long") stays a pure function that a test can interrogate directly, without
driving a loop to find out what it decided.
"""

from __future__ import annotations

import time

from .._errors import ProviderError
from .http import Attempt, Response, RetryPolicy, Transport

__all__ = ["request_with_retry"]

_DEFAULT = RetryPolicy()


def request_with_retry(transport: Transport, url: str, body: bytes, *,
                       headers: dict[str, str] | None = None,
                       timeout: float = 60.0,
                       policy: RetryPolicy = _DEFAULT) -> bytes:
    """Send `body` to `url`, retrying transient failures. Returns the response
    body, or raises ProviderError carrying the upstream status.

    A connection error is retried too: there is no status to classify, but the
    request never landed, so replaying it is safe.
    """
    last: Response | Exception | None = None
    for number in range(policy.max_retries + 1):
        outcome = _attempt(transport, url, body, headers or {}, timeout)
        if isinstance(outcome, Response) and outcome.ok:
            return outcome.body
        last = outcome
        if number == policy.max_retries or not _retryable(outcome, policy):
            break
        seen = outcome.headers if isinstance(outcome, Response) else {}
        time.sleep(policy.delay(Attempt(number=number, headers=seen)))
    # `from` keeps the causes chain: a wrapped failure stays diagnosable, and
    # anything upstream that classifies by walking __cause__ still can.
    raise _error(url, last) from (last if isinstance(last, BaseException) else None)


def _attempt(transport: Transport, url: str, body: bytes,
             headers: dict[str, str], timeout: float) -> Response | Exception:
    """One send. A transport failure is RETURNED, not raised, so the loop
    above classifies both outcomes in one place."""
    try:
        return transport.send(url, body, headers, timeout)
    except Exception as err:              # noqa: BLE001 — classified by the caller
        return err


def _retryable(outcome: Response | Exception, policy: RetryPolicy) -> bool:
    if isinstance(outcome, Response):
        return policy.should_retry(outcome.status)
    return True                            # the request never landed


def _error(url: str, last: Response | Exception | None) -> ProviderError:
    """One failure type out, whatever went wrong: a caller catching a provider
    problem should not also have to know urllib's exception tree."""
    if isinstance(last, Response):
        detail = last.body[:200].decode("utf-8", "replace").strip()
        return ProviderError(f"{url} failed with HTTP {last.status}"
                             f"{f': {detail}' if detail else ''}", status=last.status)
    return ProviderError(f"{url} unreachable: {last}")
