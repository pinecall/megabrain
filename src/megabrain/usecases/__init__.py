"""The use cases: one file per verb, sync, returning contracts.

Every transport — CLI, MCP, HTTP — calls THESE, so a behaviour is implemented
once and three surfaces cannot drift apart. The layer is thin by design and
earns its place with the decisions the engine refuses to make: which
repository a path belongs to, and what a caller who said nothing should get.

Sync all the way down. megabrain is numpy and sqlite; the HTTP edge may be
async and calls into here from a threadpool, but there is no async twin of the
engine and never will be.
"""

from __future__ import annotations

from ._root import resolve_root
from .build import build_index
from .get import get_code
from .search import search

__all__ = ["resolve_root", "build_index", "search", "get_code"]
