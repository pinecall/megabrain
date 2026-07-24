"""Assembling the bundle: rank, tier, then let the floors add what fusion lost.

CORE carries full code for the few files that clearly answer the question;
RELATED is a map — file, best span, symbols — which costs a fraction of the
tokens and is enough to decide whether to open it.
"""

from __future__ import annotations

import time

from ..._arrays import Matrix
from ...contracts import AnchorHit, Bundle, Tier1File
from ...storage.model import ChunkMeta
from .._render import to_hit
from ..params import RetrievalParams
from ..scoring.pipeline import score_chunks
from ..state import SearchState
from ._rank import Ranking, core_chunks, core_files, rank_files
from ._related import related_entry
from .floors import anchor_chunks, file_floor

__all__ = ["search_with_state"]


def search_with_state(state: SearchState, query: str, *,
                      path_filter: str | None = None,
                      content: str | None = None,
                      scored: tuple[list[ChunkMeta], Matrix] | None = None) -> Bundle:
    """The full bundle for one query.

    `scored` lets a caller that already computed the scores reuse them, so a
    view needing both the raw scores and the bundle scores exactly once.
    """
    started = time.perf_counter()
    metas, fused = scored or score_chunks(state, query, path_filter=path_filter,
                                          content=content)  # type: ignore[arg-type]
    ranking = rank_files(metas, fused)
    params = state.params

    candidates = ranking.top(params.cand_files)
    neighbours = _neighbours(state, candidates, ranking, params)
    core = core_files(ranking, params)
    # `query_vector` is set by scoring, which always runs before this point —
    # either here or in the caller that passed `scored`.
    assert state.query_vector is not None      # noqa: S101
    floor = file_floor(metas=metas, all_metas=state.metas, all_chunks=state.chunks,
                       query_vector=state.query_vector,
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
        anchors=_anchors(query, metas, fused, params),
        ms=int((time.perf_counter() - started) * 1000),
    )


def _anchors(query: str, metas: list[ChunkMeta], fused: Matrix,
             params: RetrievalParams) -> list[AnchorHit]:
    """Chunks the lexical floor pulled in, as spans rather than bodies.

    The span is what makes it actionable: the reader opens exactly the lines
    holding the identifier they asked about, instead of a whole file.
    """
    return [AnchorHit(file=metas[i].file, start_line=metas[i].start_line,
                      end_line=metas[i].end_line, terms=terms)
            for i, terms in anchor_chunks(query, metas, fused, params).items()]


def _neighbours(state: SearchState, candidates: list[str], ranking: Ranking,
                params: RetrievalParams) -> list[str]:
    """Graph neighbours of the strongest few files.

    Only the top three seed this: an import edge is evidence about the file it
    came from, and past the leaders that evidence is about something the query
    barely matched. Neighbours are ordered by their OWN score — the graph
    supplies candidates, it never ranks.
    """
    reachable: set[str] = set()
    for relpath in candidates[:3]:
        reachable |= state.store.graph.neighbors(relpath)
    reachable -= set(candidates)
    scored = reachable & set(ranking.order)
    return sorted(scored, key=lambda f: -ranking.best_of[f])[:params.graph_extras]


def _core(state: SearchState, relpath: str, ranking: Ranking, metas: list[ChunkMeta],
          fused: Matrix, bundle_files: list[str]) -> Tier1File:
    indexes = core_chunks(ranking.chunks_of[relpath], fused, state.params)
    indexes.sort(key=lambda i: metas[i].start_line)      # read top to bottom
    return Tier1File(
        file=relpath,
        score=ranking.best_of[relpath],
        chunks=[to_hit(metas[i], float(fused[i])) for i in indexes],
        symbols=[s for s in state.store.symbols.read_for(relpath)],  # type: ignore[misc]
        neighbors=sorted(state.store.graph.neighbors(relpath) & set(bundle_files)),
    )
