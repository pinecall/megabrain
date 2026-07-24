"""Is this endpoint a server on this machine?

One question, one place. It decides whether a credential is required at all,
so getting it wrong in either direction is expensive: too strict refuses a
working local setup, too loose sends a key-free request to a stranger.
"""

from __future__ import annotations

from urllib.parse import urlsplit

__all__ = ["is_local_url"]

# `urlsplit` unwraps the brackets around an IPv6 literal, so `[::1]` arrives
# here as `::1`.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1",
                          "host.docker.internal"})


def is_local_url(url: str) -> bool:
    """True for Ollama, LM Studio, vLLM and friends — endpoints that speak the
    OpenAI shape and ignore the Authorization header.

    Matched on the HOST, and parsed rather than searched for as a substring:
    `https://localhost.example.com/v1` and `https://api.example.com/localhost/v1`
    are remote services, and `user@evil.com` or a bracketed IPv6 literal is
    exactly what a hand-rolled check reads as something it is not.
    """
    return (urlsplit(url).hostname or "").lower() in _LOCAL_HOSTS
