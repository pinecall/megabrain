"""Structured engine errors: a small taxonomy every boundary maps ONCE.

Errors are data, not strings. Each carries a stable machine `code` (for MCP
payloads and logs) and an `http_status` (for the HTTP transport), so a frontend
translates the TYPE in exactly one catch site: the CLI prints one line and
exits 2, HTTP maps to a status without leaking internals, MCP returns
`error (<code>)` with isError.

Back-compat by construction: each subclass ALSO inherits the builtin it
replaced, so a 1.x caller's `except ValueError` / `except RuntimeError` keeps
working across the 2.0 boundary — the same trick as json.JSONDecodeError.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["MegabrainError", "IndexNotFound", "EmptyIndex", "MissingCredential",
           "ProviderError", "UnknownTool"]


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
        return cls(f"no megabrain index at or above {path} — run `megabrain index` "
                   f"on the repo root (looked for .megabrain/db.sqlite up the tree)")


class EmptyIndex(MegabrainError, RuntimeError):
    """The index exists but holds no chunks."""

    code = "empty_index"
    http_status = 404

    @classmethod
    def at(cls, path: str | Path | None = None) -> "EmptyIndex":
        return cls(f"index{f' at {path}' if path else ''} is empty — run: megabrain index")


class MissingCredential(MegabrainError, RuntimeError):
    """A required provider credential is not configured."""

    code = "missing_credential"
    http_status = 503

    @classmethod
    def named(cls, name: str) -> "MissingCredential":
        return cls(f"{name} is not set (export it, or add it to your shell profile)")


class ProviderError(MegabrainError, RuntimeError):
    """An upstream embedding/chat endpoint failed after retries."""

    code = "provider_error"
    http_status = 502

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        """The upstream HTTP status, or None when the request never resolved."""


class UnknownTool(MegabrainError, ValueError):
    """An MCP tools/call named a tool this server does not expose."""

    code = "unknown_tool"
    http_status = 404
