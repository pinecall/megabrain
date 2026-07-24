"""Scoring: every candidate chunk gets a number, and nothing is ranked yet.

One embedding call, then pure array arithmetic. Deterministic and repeatable —
the same query against the same index gives the same scores, which is what
makes a regression measurable at all.
"""

from __future__ import annotations

from typing import Callable

from ..._arrays import Matrix
from ..._errors import EmptyIndex
from ..._types import Content
from ...storage.model import ChunkMeta
from ..paths import under
from ..state import SearchState
from .context import build_context
from .lanes import LANES

__all__ = ["score_chunks", "DOC_EXTENSIONS"]

DOC_EXTENSIONS = (".md", ".markdown", ".mdx")


def score_chunks(state: SearchState, query: str, *,
                 path_filter: str | None = None,
                 content: Content | None = None) -> tuple[list[ChunkMeta], Matrix]:
    """Fused relevance for every candidate chunk, index-aligned with the metas.

    Filtering happens BEFORE scoring, not after: restricting a finished ranking
    would cap the answer at however many wanted files happened to outrank the
    unwanted ones.
    """
    if not state.metas:
        raise EmptyIndex.at(state.store.root)
    metas, chunks = _candidates(state, path_filter, content)
    # The ONE embedding call of a query. Stashed on the state because the
    # recall floor needs the same vector, and embedding a query twice would
    # double the only network cost on this path.
    vector = state.embedder.embed([query])[0]
    state.query_vector = vector

    ctx = build_context(query=query, params=state.params, metas=metas, chunks=chunks,
                        file_paths=state.file_paths, files=state.files,
                        query_vector=vector)
    fused: Matrix | None = None
    for lane in LANES:
        if lane.applies(ctx):
            fused = lane.apply(ctx, fused)
    assert fused is not None      # noqa: S101 — LANES is non-empty by construction
    return metas, fused


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
