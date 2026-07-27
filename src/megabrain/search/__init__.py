"""Retrieval: question in, ranked code out. Layer 3, deterministic.

No language model reaches this package or anything it imports. LLM lanes live
in `enrich/` and take a finished bundle; a test in tests/architecture is the
fence between them, so the rule cannot quietly stop being true.
"""

from __future__ import annotations

from .bundle import search_with_state
from .params import DEFAULT_PARAMS, RetrievalParams
from .scoring import score_chunks
from .search import search
from .state import SearchState, load_state

__all__ = ["search", "search_with_state", "score_chunks", "load_state",
           "SearchState", "RetrievalParams", "DEFAULT_PARAMS"]
