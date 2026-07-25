"""Errors from the outside world: credentials and upstream endpoints.

Kept apart from the index errors because they are a different KIND of failure —
nothing is wrong with the repository, the environment is not configured or a
service is down — and because a caller that wants to retry cares about exactly
this set.
"""

from __future__ import annotations

from ._errors import MegabrainError

__all__ = ["MissingCredential", "MissingAPIKey", "ProviderError"]


class MissingCredential(MegabrainError, RuntimeError):
    """A required provider credential is not configured.

    `code` keeps its released spelling: a class name is internal vocabulary and
    improving it is free, but `code` is a WIRE value that MCP payloads, HTTP
    bodies and log pipelines switch on.
    """

    code = "missing_api_key"
    http_status = 503

    @classmethod
    def named(cls, name: str) -> "MissingCredential":
        return cls(f"{name} is not set (export it, or add it to your shell profile)")


# The released spelling: what code in the wild catches, so it stays. Same class.
MissingAPIKey = MissingCredential


class ProviderError(MegabrainError, RuntimeError):
    """An upstream embedding/chat endpoint failed after retries."""

    code = "provider_error"
    http_status = 502

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status      # the upstream status, None if it never resolved
