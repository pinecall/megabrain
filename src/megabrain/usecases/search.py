"""The verb `search`: one question, one bundle.

The engine's own `search()` is the neutral primitive — it deliberately refuses
to decide whether prose should compete with code, because that is policy. This
is where policy lives.
"""

from __future__ import annotations

from pathlib import Path

from .._types import Content
from ..contracts import Bundle, Tier2File
from ..search.bundle import search_with_state
from ..search.bundle._rank import rank_files
from ..search.scoring.pipeline import Scored, score_chunks
from ..search.state import SearchState, load_state
from ..storage.locate import resolve_root

__all__ = ["search"]


def search(start: Path | str, query: str, *, path_filter: str | None = None,
           content: Content | None = None, rerank: bool = False,
           expand: bool = False, embedder: object = None) -> Bundle:
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

    `expand` buys RECALL where `rerank` buys ORDER, and they compose in that
    direction: the judge can only reorder what the pool holds, so widening
    first is what lets it promote something the question's wording never
    reached. `embedder` is an injection seam for tests.
    """
    root = resolve_root(start)
    state = load_state(root)
    if embedder is not None:
        state.embedder = embedder    # type: ignore[assignment]
    with state:
        # Scored once and handed to both: the expander needs the same ranking
        # the bundle was built from, and scoring it twice would let the two
        # disagree for no reason a reader could ever see.
        scored = score_chunks(state, query, path_filter=path_filter, content=content)
        bundle = search_with_state(state, query, path_filter=path_filter,
                                   content=content, scored=scored)
        if expand:
            bundle = _expanded(bundle, root, state, scored)
    return _judged(bundle, root) if rerank else bundle


def _expanded(bundle: Bundle, root: Path, state: SearchState,
              scored: Scored) -> Bundle:
    """Widen through the expander lane, resolving names against the SAME index.

    Shares the repo's `rerank` model rather than adding a second knob: both
    lanes want the same thing from a model — a cheap, fast opinion over text a
    deterministic pipeline already chose — and a repo that configured neither
    gets neither, which is the honest default.
    """
    from ..enrich.expand import expand as widen
    from ..enrich.rerank import judge_provider
    from ..project import load_project
    from ..search.bundle.widen import term_entries

    provider = judge_provider(load_project(root).rerank_model)
    if provider is None:
        return bundle

    ranking = rank_files(scored.metas, scored.fused)

    def resolve(terms: list[str], held: set[str]) -> list[Tier2File]:
        return term_entries(state, terms, ranking=ranking, metas=scored.metas,
                            params=state.params, held=held)

    return widen(bundle, provider, resolve)


def _judged(bundle: Bundle, root: Path) -> Bundle:
    """Reorder through the judge lane with the model this REPO chose.

    No provider configured is not an error here: the lane is an optimisation,
    so an unconfigured deployment simply does not get it.
    """
    from ..enrich.rerank import judge_provider
    from ..enrich.rerank import rerank as judge
    from ..project import load_project

    provider = judge_provider(load_project(root).rerank_model)
    return judge(bundle, provider) if provider is not None else bundle
