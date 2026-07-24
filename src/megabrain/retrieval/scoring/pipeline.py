"""Scoring: every candidate chunk gets a number, and nothing is ranked yet.

One embedding call, then pure array arithmetic. Deterministic and repeatable —
the same query against the same index gives the same scores, which is what
makes a regression measurable at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..._arrays import Matrix, Vector
from ..._errors import EmptyIndex
from ..._types import Content
from ...storage.model import ChunkMeta
from ..paths import under
from ..state import SearchState
from ._space import require_same_space
from .context import build_context
from .lanes import BASE, LANES

__all__ = ["Scored", "score_chunks", "DOC_EXTENSIONS"]

DOC_EXTENSIONS = (".md", ".markdown", ".mdx")


@dataclass(frozen=True, slots=True)
class Scored:
    """One query's scores, and the vector they were computed from.

    The vector travels WITH the scores because later stages need it — the
    recall floor scores raw cosine against the same query, and retrieval must
    never embed the same text twice. Handing it over as a field makes that a
    parameter; leaving it on the shared state made it a convention, where every
    later stage simply trusted that whoever scored last scored THIS query.
    """

    metas: list[ChunkMeta]
    fused: Matrix               # score i belongs to metas[i]
    query_vector: Vector


def score_chunks(state: SearchState, query: str, *,
                 path_filter: str | None = None,
                 content: Content | None = None) -> Scored:
    """Fused relevance for every candidate chunk, index-aligned with the metas.

    Filtering happens BEFORE scoring, not after: restricting a finished ranking
    would cap the answer at however many wanted files happened to outrank the
    unwanted ones.
    """
    if not state.metas:
        raise EmptyIndex.at(state.store.root)
    metas, chunks = _candidates(state, path_filter, content)
    vector = state.embedder.embed([query])[0]      # the ONE embedding of a query
    require_same_space(state, vector)
    ctx = build_context(query=query, params=state.params, metas=metas, chunks=chunks,
                        file_paths=state.file_paths, files=state.files,
                        query_vector=vector)
    fused = BASE.apply(ctx)
    for lane in LANES:
        if lane.applies(ctx):
            fused = lane.apply(ctx, fused)
    return Scored(metas=metas, fused=fused, query_vector=vector)


def _candidates(state: SearchState, path_filter: str | None,
                content: Content | None) -> tuple[list[ChunkMeta], Matrix]:
    metas, chunks = state.metas, state.chunks
    if path_filter:
        metas, chunks = _keep(metas, chunks, lambda m: under(m.file, path_filter))
    if content is not None:
        wanted = content == "docs"
        metas, chunks = _keep(metas, chunks, lambda m: _is_doc(m.file) is wanted)
    return metas, chunks


def _keep(metas: list[ChunkMeta], chunks: Matrix,
          predicate: Callable[[ChunkMeta], bool]) -> tuple[list[ChunkMeta], Matrix]:
    """Narrow the candidate set — but FAIL OPEN.

    An empty result means the filter matched nothing: a stale sub-path, or docs
    asked of a repository that has none. Returning nothing there is a silent
    lie about the repository; returning everything is a visibly wider answer
    the caller can see and correct.
    """
    keep = [i for i, m in enumerate(metas) if predicate(m)]
    if not keep or len(keep) == len(metas):
        return metas, chunks
    return [metas[i] for i in keep], chunks[keep]


def _is_doc(relpath: str) -> bool:
    return relpath.lower().endswith(DOC_EXTENSIONS)
