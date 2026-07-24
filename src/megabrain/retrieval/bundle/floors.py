"""The two recall floors.

Fusion is a ranking OPINION, never a recall gate. Both floors exist to stop an
opinion from becoming one, and both are PURE ADDITIONS: they append to the tail
and never reorder or displace anything, so bundle completeness can only rise.

That property is what makes them safe to have at all — a floor that could push
something out would be a second ranker wearing a safety vest.
"""

from __future__ import annotations

import re

import numpy as np

from ..._arrays import Matrix, Vector
from ...storage.model import ChunkMeta
from ..params import RetrievalParams
from ..paths import is_demo, is_test

__all__ = ["file_floor", "anchor_chunks"]

# Multi-word identifiers only. A rare single word is usually prose; a rare
# multi-word identifier is a name the question QUOTED from the code.
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")


def file_floor(*, metas: list[ChunkMeta], all_metas: list[ChunkMeta], all_chunks: Matrix,
               query_vector: Vector, already: set[str], params: RetrievalParams) -> list[str]:
    """Files owning a top-N RAW-DENSE chunk that the fused ranking dropped.

    File fusion lifts every chunk of a file that matches as a whole, which
    buries the small helper living inside ANOTHER feature's file — and that is
    what prior art looks like by construction: reusable logic ends up under a
    different name in a different subsystem. A file whose chunk is genuinely
    among the nearest by raw cosine is owed a slot regardless of what fusion
    thought of its neighbours.

    Tests are skipped: they are deliberately down-weighted elsewhere, and
    re-admitting them here would undo that on purpose-built vocabulary matches.
    """
    if not params.recall_floor_top:
        return []
    row_of = {m.id: i for i, m in enumerate(all_metas)}
    rows = np.array([row_of.get(m.id, -1) for m in metas], dtype=np.int64)
    present = np.flatnonzero(rows >= 0)  # pyright: ignore[reportUnknownMemberType]
    if not present.size:
        return []
    dense = all_chunks[rows[present]] @ query_vector
    owed: list[str] = []
    seen = set(already)
    for position in np.argsort(-dense)[:params.recall_floor_top]:  # pyright: ignore[reportUnknownMemberType]
        relpath = metas[int(present[int(position)])].file
        if relpath in seen or is_test(relpath):
            continue
        owed.append(relpath)
        seen.add(relpath)
    return owed


def anchor_chunks(query: str, metas: list[ChunkMeta], fused: Matrix,
                  params: RetrievalParams) -> dict[int, list[str]]:
    """Chunks holding a rare identifier the query quoted verbatim.

    The file floor one level down. Fusion lifts every chunk of a matching file,
    so a monolithic file's chunks nearly tie and a per-file cap then cuts an
    arbitrary top-N out of a flat distribution — dropping the exact capture site
    that contains the query's own rare name.

    What discriminates it is lexical, not semantic: the identifier is literally
    in the text. Deterministic, no model. Tests and demos are excluded from both
    the count and the floor — they quote the same identifiers by design, which
    inflates the document frequency and hides the real definition behind them.
    """
    terms = [t for t in dict.fromkeys(_IDENT.findall(query))
             if "_" in t or any(c.isupper() for c in t[1:])]
    if not terms or not params.anchor_chunk_cap:
        return {}
    implementation = [i for i, m in enumerate(metas)
                      if not is_test(m.file) and not is_demo(m.file)]
    hits: dict[int, list[str]] = {}
    for term in terms:
        matched = [i for i in implementation if term in (metas[i].text or "")]
        if 0 < len(matched) <= params.anchor_df_cap:
            for i in matched:
                hits.setdefault(i, []).append(term)
    ranked = sorted(hits, key=lambda i: (-len(hits[i]), -float(fused[i])))
    return {i: hits[i] for i in ranked[:params.anchor_chunk_cap]}
