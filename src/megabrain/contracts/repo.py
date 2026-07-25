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
    cards: int
    """How many files have a mental-map card — 0 means `brief` cannot answer yet.

    Surfaced because the Brief tab silently needs `megabrain study` to have run,
    and a rail that showed every repository identically made that impossible to
    know before clicking. One SQL count; the confusion was free to remove."""
