"""Who may call what — three independent gates, because they answer different
questions: is this caller allowed in at all, may this deployment change
anything, and is one caller taking more than its share."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

__all__ = ["Guard", "Policy", "OPEN_PATHS", "WRITING_PATHS"]

# Reachable without a token even when one is configured: a health check that
# needs a credential cannot be used by the thing that restarts the server.
OPEN_PATHS = frozenset({"/", "/health", "/config"})

# Routes that CHANGE something — listed, not inferred from the method: a
# read-only promise that depends on future routes' labels is not much of one.
WRITING_PATHS = frozenset({"/index", "/index/stream", "/repos/add"})

# Routes that cost MONEY per call: a read-only public box still must not let
# one caller spend the deployment's budget on walkthroughs.
BILLED_PATHS = frozenset({"/ask", "/ask/stream"})

WINDOW = 60.0                      # the sliding minute every meter here shares


def _no_callers() -> "dict[str, deque[float]]":
    return {}


@dataclass(frozen=True, slots=True)
class Policy:
    token: str = ""
    readonly: bool = False
    rate_limit: int = 0            # requests per minute per caller; 0 = unmetered
    trust_proxy: bool = False      # behind nginx the socket is always the proxy


@dataclass(slots=True)
class Guard:
    """Enforces one policy. Shared across threads, so the meter takes a lock."""

    policy: Policy
    _hits: "dict[str, deque[float]]" = field(default_factory=_no_callers)
    _lock: Lock = field(default_factory=Lock)
    _swept: float = 0.0

    def caller_of(self, remote: str, forwarded: str) -> str:
        """The first `X-Forwarded-For` hop — only when the operator SAID a
        proxy sits in front. On a directly-exposed box the header lets any
        caller mint a fresh identity per request, so the default is off."""
        if self.policy.trust_proxy and forwarded.strip():
            return forwarded.split(",")[0].strip()
        return remote

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
        """A sliding minute per caller — a fixed window would let a caller
        spend its whole allowance at 0:59 and again at 1:00, which is the
        burst the limit exists to prevent."""
        if not self.policy.rate_limit:
            return True
        with self._lock:
            self._forget_departed(now)
            hits = self._hits.setdefault(caller, deque())
            while hits and now - hits[0] > WINDOW:
                hits.popleft()
            if len(hits) >= self.policy.rate_limit:
                return False
            hits.append(now)
            return True

    def _forget_departed(self, now: float) -> None:
        """Drop callers whose whole window expired — at most one sweep a minute,
        so a request never pays an O(callers) scan. Without it the map holds one
        entry per distinct address forever, and a forwarded header makes
        "distinct address" a thing an attacker types."""
        if now - self._swept < WINDOW:
            return
        self._swept = now
        for key in [k for k, hits in self._hits.items()
                    if not hits or now - hits[-1] > WINDOW]:
            del self._hits[key]
