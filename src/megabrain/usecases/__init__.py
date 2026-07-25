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

from ..storage.locate import resolve_root
from .ask import ask
from .brief import brief
from .build import build_index
from .freshness import Freshness, freshness
from .get import get_code
from .repos import known, remember
from .scan import scan
from .search import search
from .study import study

__all__ = ["resolve_root", "build_index", "search", "ask", "get_code",
           "known", "remember", "scan", "study", "brief",
           "freshness", "Freshness"]
