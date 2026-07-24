"""Structured engine errors: a small taxonomy every boundary maps ONCE.

Errors are data, not strings. Each carries a stable machine `code` (for MCP
payloads and logs) and an `http_status`, so every transport translates the TYPE
in exactly one catch site instead of matching on message text.

Back-compat by construction: each subclass ALSO inherits the builtin a caller
would plausibly have been catching before the typed error existed, so an
`except ValueError` in the wild keeps working across a major boundary — the
same trick as json.JSONDecodeError(ValueError). Every message names what to DO:
it is the only thing a stuck user reads.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["MegabrainError", "IndexNotFound", "EmptyIndex", "ModelMismatch",
           "MissingCredential", "MissingAPIKey", "ProviderError"]


class MegabrainError(Exception):
    """Root. `except MegabrainError` catches everything the engine raises."""

    code = "error"
    http_status = 500


class IndexNotFound(MegabrainError, ValueError):
    """No `.megabrain/db.sqlite` at or above the given path."""

    code = "index_not_found"
    http_status = 404

    @classmethod
    def at(cls, path: str | Path) -> "IndexNotFound":
        return cls(f"no megabrain index at or above {path} — "
                   f"run `megabrain index` on the repo root")


class EmptyIndex(MegabrainError, RuntimeError):
    """The index exists but holds no chunks."""

    code = "empty_index"
    http_status = 404

    @classmethod
    def at(cls, path: str | Path | None = None) -> "EmptyIndex":
        return cls(f"index{f' at {path}' if path else ''} is empty — run: megabrain index")


class ModelMismatch(MegabrainError, RuntimeError):
    """The query's embedding model is not the one that built the index."""

    code = "model_mismatch"
    http_status = 409

    @classmethod
    def between(cls, *, query_model: str, query_dims: int, index_dims: int,
                index_model: object) -> "ModelMismatch":
        return cls(f"index built with {index_model} at {index_dims} dimensions, "
                   f"but {query_model} returns {query_dims} — different vector "
                   f"spaces. Re-run `megabrain index`, or set the old model back.")


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
