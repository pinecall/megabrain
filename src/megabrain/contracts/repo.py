"""What this machine knows about an indexed repository.

The studio's repo rail and `megabrain repos` read this. It is deliberately
small: a registry that duplicates the index's own numbers is a second source
of truth, and it is always the one that goes stale.
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["RepoEntry"]


class RepoEntry(TypedDict):
    """One indexed repository, as of right now."""

    path: str
    name: str
    files: int
    chunks: int
