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

from ..ask.ask import ask
from ..grep.grep import grep
from ..indexing.build import build_index
from ..search import search
from ..storage.locate import resolve_root
from .freshness import Freshness, freshness
from .get import get_code
from .repos import known, remember
from .scan import scan
from .starters import Starters, starters_for

__all__ = ["resolve_root", "build_index", "search", "ask", "grep", "get_code",
           "known", "remember", "scan",
           "freshness", "Freshness", "starters_for", "Starters"]
