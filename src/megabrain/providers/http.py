"""One HTTP attempt, and the policy that decides whether to make another.

The transport is a Protocol, so tests drive a script instead of a socket and
the engine stays offline-testable end to end. Everything here is deterministic
except the jitter, which is the point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import random
from typing import Protocol

__all__ = ["Response", "Transport", "Attempt", "RetryPolicy", "RETRYABLE"]


def _no_headers() -> dict[str, str]:
    """A typed empty default. `default_factory=dict` reads as an untyped dict
    to a strict checker, which then loses the key and value types everywhere
    the field is used."""
    return {}

# Statuses worth trying again: the request was fine, the server was not.
# 408 timeout · 409 lock contention · 429 rate limit · 5xx server fault.
RETRYABLE = frozenset({408, 409, 429})


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=_no_headers)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class Transport(Protocol):
    """The seam. `UrllibTransport` in production, a script in tests."""

    def send(self, url: str, body: bytes, headers: dict[str, str],
             timeout: float) -> Response: ...


@dataclass(frozen=True, slots=True)
class Attempt:
    """What the policy gets to reason about: which try this is, and whatever
    the server said about when to come back."""

    number: int                          # 0 on the first attempt
    headers: dict[str, str] = field(default_factory=_no_headers)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_retries: int = 2
    initial_delay: float = 0.5
    max_delay: float = 8.0
    max_honoured_retry_after: float = 60.0

    def should_retry(self, status: int) -> bool:
        return status in RETRYABLE or status >= 500

    def delay(self, attempt: Attempt) -> float:
        """Seconds to wait before the next attempt.

        A server that says when it will be ready is obeyed, within reason: an
        hour-long Retry-After is a misconfiguration, and honouring it hangs the
        caller with no way to see why. Otherwise exponential backoff, capped,
        with jitter that only ever SUBTRACTS — a multiplier above 1.0 would let
        the wait exceed max_delay, which then is not a maximum.
        """
        asked = _retry_after(attempt.headers)
        if asked is not None and 0 < asked <= self.max_honoured_retry_after:
            return min(asked, self.max_delay)
        # The exponent is capped independently of max_retries so a caller
        # passing a very large number cannot overflow the power.
        base = self.initial_delay * 2.0 ** min(attempt.number, 16)
        return min(base, self.max_delay) * (1 - 0.25 * random())


def _retry_after(headers: dict[str, str]) -> float | None:
    """`retry-after-ms` first: non-standard, but finer-grained than whole
    seconds, so a server that says 1500ms is not rounded up to two."""
    for key, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
        raw = headers.get(key)
        if raw is None:
            continue
        try:
            return float(raw) * scale
        except ValueError:
            continue
    return None
