"""Who may call what.

Three independent gates, because they answer different questions: is this
caller allowed in at all, may this deployment change anything, and is one
caller taking more than its share.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

__all__ = ["Guard", "Policy", "OPEN_PATHS", "WRITING_PATHS"]

# Reachable without a token even when one is configured: a health check that
# needs a credential cannot be used by the thing that restarts the server, and
# the studio has to load before it can ask the user for anything.
OPEN_PATHS = frozenset({"/", "/health", "/config"})

# Routes that CHANGE something. Listed rather than inferred from the method:
# a read-only deployment is a promise about effects, and a promise that depends
# on every future route being labelled correctly is not one.
WRITING_PATHS = frozenset({"/index", "/index/stream", "/repos/add"})


def _no_hits() -> "deque[float]":
    return deque()


def _no_callers() -> "dict[str, deque[float]]":
    return {}


@dataclass(frozen=True, slots=True)
class Policy:
    token: str = ""
    readonly: bool = False
    rate_limit: int = 0            # requests per minute per caller; 0 = unmetered


@dataclass(slots=True)
class Guard:
    """Enforces one policy. Shared across threads, so the meter takes a lock."""

    policy: Policy
    _hits: "dict[str, deque[float]]" = field(default_factory=_no_callers)
    _lock: Lock = field(default_factory=Lock)

    def refuse(self, path: str, *, authorization: str, caller: str,
               now: float | None = None) -> tuple[int, str] | None:
        """`(status, message)` when the request must not proceed, else None."""
        if not self._authorised(path, authorization):
            return 401, "missing or invalid token"
        if self.policy.readonly and path in WRITING_PATHS:
            return 403, "read-only server — indexing is disabled here"
        if not self._within_rate(caller, now if now is not None else time.monotonic()):
            return 429, f"rate limit: {self.policy.rate_limit} requests per minute"
        return None

    def _authorised(self, path: str, authorization: str) -> bool:
        if not self.policy.token or path in OPEN_PATHS:
            return True
        return authorization == f"Bearer {self.policy.token}"

    def _within_rate(self, caller: str, now: float) -> bool:
        """A sliding minute per caller.

        Sliding rather than a fixed window: a fixed one lets a caller spend
        its whole allowance at 0:59 and again at 1:00, which is the burst the
        limit exists to prevent.
        """
        if not self.policy.rate_limit:
            return True
        with self._lock:
            hits = self._hits.setdefault(caller, _no_hits())
            while hits and now - hits[0] > 60.0:
                hits.popleft()
            if len(hits) >= self.policy.rate_limit:
                return False
            hits.append(now)
            return True
