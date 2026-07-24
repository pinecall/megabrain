"""Assembling the bundle: rank, tier, then let the floors add what fusion lost.

CORE carries full code for the few files that clearly answer the question;
RELATED is a map — file, best span, symbols — which costs a fraction of the
tokens and is enough to decide whether to open it.
"""

from __future__ import annotations

import time

from ..._arrays import Matrix
from ..._types import Content
from ...contracts import Bundle, Tier1File
from ...storage.model import ChunkMeta
from ..scoring.pipeline import Scored, score_chunks
from ..state import SearchState
from ._anchors import render_anchors
from ._convert import to_hit, to_outline
from ._rank import Ranking, core_chunks, core_files, rank_files
from ._related import neighbours_of, related_entry
from .floors import file_floor

__all__ = ["search_with_state"]


def search_with_state(state: SearchState, query: str, *,
                      path_filter: str | None = None,
                      content: Content | None = None,
                      scored: Scored | None = None) -> Bundle:
    """The full bundle for one query.

    `scored` lets a caller that already computed the scores reuse them, so a
    view needing both the raw scores and the bundle scores exactly once. It
    carries its own query vector, so a reused result cannot be paired with a
    vector from some other query.
    """
    started = time.perf_counter()
    scored = scored or score_chunks(state, query, path_filter=path_filter,
                                    content=content)
    metas, fused = scored.metas, scored.fused
    ranking = rank_files(metas, fused)
    params = state.params

    candidates = ranking.top(params.cand_files)
    neighbours = neighbours_of(state, candidates, ranking, params)
    core = core_files(ranking, params)
    floor = file_floor(metas=metas, all_metas=state.metas, all_chunks=state.chunks,
                       query_vector=scored.query_vector,
                       already=set(candidates) | set(neighbours), params=params)

    related = [f for f in candidates if f not in core] + neighbours + floor
    return Bundle(
        query=query,
        repo=state.repo,
        tier1=[_core(state, f, ranking, metas, fused, candidates + neighbours)
               for f in core],
        tier2=[related_entry(state, f, ranking, metas,
                             via_graph=f in neighbours, params=params)
               for f in related],
        flows=[],
        anchors=render_anchors(query, metas, fused, params),
        ms=int((time.perf_counter() - started) * 1000),
    )


def _core(state: SearchState, relpath: str, ranking: Ranking, metas: list[ChunkMeta],
          fused: Matrix, bundle_files: list[str]) -> Tier1File:
    indexes = core_chunks(ranking.chunks_of[relpath], fused, state.params)
    indexes.sort(key=lambda i: metas[i].start_line)      # read top to bottom
    return Tier1File(
        file=relpath,
        score=ranking.best_of[relpath],
        chunks=[to_hit(metas[i], float(fused[i])) for i in indexes],
        # Through the SAME narrowing door tier-2 uses. A raw storage row has
        # seven keys (including `decorators`) where the contract declares six;
        # emitting it directly once shipped green because only fixtures from
        # the previous engine were ever shape-checked — no fixture could
        # contain this engine's leak.
        symbols=[to_outline(s) for s in state.store.symbols.read_for(relpath)],
        neighbors=sorted(state.store.graph.neighbors(relpath) & set(bundle_files)),
    )
