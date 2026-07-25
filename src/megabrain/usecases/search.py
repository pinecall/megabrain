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
           content: Content | None = None, rerank: bool = False,
           embedder: object = None) -> Bundle:
    """Answer `query` for whichever repository `start` belongs to.

    `content=None` lets code and docs compete, which is right for a question
    whose shape nobody has inspected. A caller that KNOWS it wants one side
    says so — the decision is visible at the call site rather than guessed
    from the query's wording, which is the kind of heuristic that is wrong
    silently and only for other people's repositories.

    `rerank` is OFF by default, and that is the shape of the whole product:
    the deterministic answer is complete on its own, and the judge lane only
    reorders it. A caller that wants better ordering asks for it and accepts
    the latency and the cost; a caller that says nothing gets an answer in
    milliseconds that never depends on a model being up.

    `embedder` is an injection seam for tests; production leaves it alone and
    gets the configured one.
    """
    state = load_state(resolve_root(start))
    if embedder is not None:
        state.embedder = embedder    # type: ignore[assignment]
    with state:
        bundle = search_with_state(state, query, path_filter=path_filter,
                                   content=content)
    return _judged(bundle) if rerank else bundle


def _judged(bundle: Bundle) -> Bundle:
    """Reorder through the judge lane, or hand back what retrieval decided.

    No provider configured is not an error here: the lane is an optimisation,
    so an unconfigured deployment simply does not get it.
    """
    from ..enrich.rerank import judge_provider
    from ..enrich.rerank import rerank as judge

    provider = judge_provider()
    return judge(bundle, provider) if provider is not None else bundle
