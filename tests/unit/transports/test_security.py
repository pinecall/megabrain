"""The guard's caller identity and its memory of them.

Behind nginx every request arrives from the proxy's address, so a rate limit
keyed on the socket punishes everyone for one abuser — and trusting the
forwarded header on a directly-exposed box lets any caller mint identities.
Both directions are pinned here.
"""

from __future__ import annotations

from megabrain.transports.http.security import Guard, Policy


def test_the_socket_address_is_the_caller_by_default() -> None:
    guard = Guard(Policy())
    assert guard.caller_of("203.0.113.9", "10.0.0.1, 172.16.0.1") == "203.0.113.9"


def test_trust_proxy_reads_the_first_forwarded_hop() -> None:
    guard = Guard(Policy(trust_proxy=True))
    assert guard.caller_of("127.0.0.1", "203.0.113.9, 172.16.0.1") == "203.0.113.9"


def test_trust_proxy_without_a_header_falls_back_to_the_socket() -> None:
    """A direct request to a trust-proxy box still has a caller."""
    guard = Guard(Policy(trust_proxy=True))
    assert guard.caller_of("203.0.113.9", "") == "203.0.113.9"


def test_the_rate_limit_separates_forwarded_callers() -> None:
    guard = Guard(Policy(rate_limit=1, trust_proxy=True))
    first = guard.caller_of("127.0.0.1", "203.0.113.9")
    second = guard.caller_of("127.0.0.1", "198.51.100.7")
    assert guard.refuse("/search", authorization="", caller=first, now=0.0) is None
    assert guard.refuse("/search", authorization="", caller=second, now=0.1) is None
    refused = guard.refuse("/search", authorization="", caller=first, now=0.2)
    assert refused is not None and refused[0] == 429


def test_departed_callers_are_forgotten() -> None:
    """The per-caller map must not grow one entry per address forever."""
    guard = Guard(Policy(rate_limit=5))
    for n in range(1000):
        guard.refuse("/search", authorization="", caller=f"10.0.0.{n}", now=float(n))
    # Every one of those windows is over a minute stale by now — one live
    # caller must be enough to reclaim them all.
    guard.refuse("/search", authorization="", caller="fresh", now=2000.0)
    assert len(guard._hits) < 10
