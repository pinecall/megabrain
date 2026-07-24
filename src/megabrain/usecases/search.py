"""The verb `search`: one question, one bundle.

The engine's own `search()` is the neutral primitive — it deliberately refuses
to decide whether prose should compete with code, because that is policy. This
is where policy lives.
"""

from __future__ import annotations

from pathlib import Path

from .._types import Content
from ..contracts import Bundle
from ..retrieval.bundle import search_with_state
from ..retrieval.state import load_state
from ._root import resolve_root

__all__ = ["search"]


def search(start: Path | str, query: str, *, path_filter: str | None = None,
           content: Content | None = None, embedder: object = None) -> Bundle:
    """Answer `query` for whichever repository `start` belongs to.

    `content=None` lets code and docs compete, which is right for a question
    whose shape nobody has inspected. A caller that KNOWS it wants one side
    says so — the decision is visible at the call site rather than guessed
    from the query's wording, which is the kind of heuristic that is wrong
    silently and only for other people's repositories.

    `embedder` is an injection seam for tests; production leaves it alone and
    gets the configured one.
    """
    state = load_state(resolve_root(start))
    if embedder is not None:
        state.embedder = embedder    # type: ignore[assignment]
    with state:
        return search_with_state(state, query, path_filter=path_filter,
                                 content=content)
