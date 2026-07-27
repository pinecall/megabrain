"""Turning per-chunk scores into a ranked set of FILES.

A file is the unit a reader opens, so retrieval ranks files by their best chunk
and keeps each file's chunks together. Ranking chunks globally instead produces
a list that jumps between six files and reads like noise.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..._arrays import Matrix
from ...storage.model import ChunkMeta
from ..params import RetrievalParams

__all__ = ["Ranking", "rank_files"]


@dataclass(frozen=True, slots=True)
class Ranking:
    order: list[str]                     # files, best first
    chunks_of: dict[str, list[int]]      # file -> chunk indexes, best first
    best_of: dict[str, float]            # file -> its best chunk's score

    def top(self, n: int) -> list[str]:
        return self.order[:n]


def rank_files(metas: list[ChunkMeta], fused: Matrix) -> Ranking:
    """Files ordered by their best chunk, with each file's chunks grouped."""
    order: list[str] = []
    chunks_of: dict[str, list[int]] = {}
    # STABLE, not the default introsort: scores tie constantly — a file whose
    # chunks are near-identical, a query that matches nothing in particular —
    # and introsort returns ties in whatever order its partitioning produced,
    # which changes with array size and numpy version. Retrieval promises the
    # same answer for the same index, so ties fall back to index order.
    #
    # numpy's argsort/flatnonzero declare partially unknown returns in their
    # shipped overloads; suppressed by rule name at the exact line rather than
    # package-wide, since the surrounding annotations are what pin the types.
    for index in np.argsort(-fused, kind="stable"):  # pyright: ignore[reportUnknownMemberType]
        relpath = metas[int(index)].file
        if relpath not in chunks_of:
            order.append(relpath)
        chunks_of.setdefault(relpath, []).append(int(index))
    return Ranking(order, chunks_of,
                   {f: float(fused[chunks_of[f][0]]) for f in order})


def core_files(ranking: Ranking, params: RetrievalParams) -> list[str]:
    """The files that get their full code rather than a map.

    Adaptive rather than a fixed count: only files within `tier1_gap` of the
    top score qualify. When one file clearly answers the question, showing three
    more at full length is noise; when several tie, they all earn it. Never
    empty — the best file is CORE even if nothing else comes close.
    """
    candidates = ranking.top(params.tier1_max)
    if not candidates:
        return []
    ceiling = ranking.best_of[candidates[0]] * params.tier1_gap
    return [f for f in candidates if ranking.best_of[f] >= ceiling] or candidates[:1]


def core_chunks(indexes: list[int], fused: Matrix, params: RetrievalParams) -> list[int]:
    """Which chunks of a CORE file are worth their full body.

    Relative to that file's own best, not to a global threshold: a strong file
    should not have its weaker halves cut just because another file scored
    higher. Capped, then sorted by line so the file reads top to bottom.
    """
    best = fused[indexes[0]]
    keep = [i for i in indexes
            if fused[i] >= best * params.chunk_keep_ratio][:params.tier1_chunk_cap]
    return keep or indexes[:1]
