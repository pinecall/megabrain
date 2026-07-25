"""Reading the arguments a model wrote.

Its own module for the same reason `http/_target` is: this is where values
from outside become the arguments a use case is called with, and every rule
about that belongs where it can be read at once. The caller here is a language
model, so the rules are stricter than for a typed client — a missing key, a
number where a string belongs, or a `limit` of one million are all ordinary
Tuesday traffic, and none of them may reach the engine as a crash.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..._types import Content
from ._missing import Missing
from ._payload import first_of, operations, optional

__all__ = ["Missing", "repo", "text", "scope", "content", "limit", "flag",
           "first_of", "optional", "operations"]

_CONTENT = ("code", "docs")
BRIEF_LIMIT = 10
BRIEF_MAX = 30


def repo(arguments: dict[str, Any]) -> Path:
    return Path(text(arguments, "repo_path"))


def text(arguments: dict[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise Missing(f"`{name}` is required, as a non-empty string")
    return value


def scope(arguments: dict[str, Any]) -> str | None:
    asked = arguments.get("scope_path")
    return asked if isinstance(asked, str) and asked.strip() else None


def content(arguments: dict[str, Any]) -> Content | None:
    """Anything that is not one of the two states is no state at all — a typo
    must not silently mean "code"."""
    asked = arguments.get("content")
    return asked if asked in _CONTENT else None    # type: ignore[return-value]


def limit(arguments: dict[str, Any]) -> int:
    """Clamped, not trusted: a request for a million files is a request to
    read the whole index into one reply."""
    asked = arguments.get("limit")
    return min(BRIEF_MAX, max(1, asked)) if isinstance(asked, int) else BRIEF_LIMIT


def flag(arguments: dict[str, Any], name: str, *, default: bool) -> bool:
    """Present-and-false is the only way to turn a defaulted flag off; a
    missing key means the caller had no opinion, which is not the same thing."""
    asked = arguments.get(name)
    return asked if isinstance(asked, bool) else default
