"""Which chunks the model is allowed to cite.

Ordered by TIER, not re-scored: retrieval already ranked these and a second
ordering here would be a second opinion nobody asked for. Tests come last —
they quote the implementation's vocabulary, so they crowd the candidate list
without explaining the mechanism.
"""

from __future__ import annotations

from ...contracts import Bundle, ChunkHit, ChunkRef
from ...retrieval.paths import is_test
from ...storage.model import ChunkMeta

__all__ = ["candidates_of", "MAX_CANDIDATES"]

MAX_CANDIDATES = 40


def candidates_of(bundle: Bundle) -> list[ChunkMeta]:
    """The chunks the model may cite, CORE first.

    Ordered by tier rather than re-scored: retrieval already ranked these, and
    a second ordering here would be a second opinion nobody asked for. Tests
    come last — they quote the implementation's vocabulary, so they crowd the
    candidate list without explaining the mechanism.
    """
    seen: set[int] = set()
    out: list[ChunkMeta] = []
    for entry in bundle["tier1"]:
        for hit in entry["chunks"]:
            if hit["id"] not in seen:
                seen.add(hit["id"])
                out.append(_meta(hit))
    for related in bundle["tier2"]:
        best = related["best_chunk"]
        if best and best["id"] not in seen:
            seen.add(best["id"])
            out.append(_meta(best))
    out.sort(key=lambda chunk: is_test(chunk.file))     # stable: tests last
    return out[:MAX_CANDIDATES]


def _meta(hit: ChunkRef | ChunkHit) -> ChunkMeta:
    """A wire chunk back to the record the splice works with.

    Typed against the CONTRACT rather than a dict: the fields are declared once
    in contracts/, so a rename there becomes an error here instead of a
    KeyError at the first ask.
    """
    return ChunkMeta(
        id=hit["id"], file=hit["file"], kind=hit["kind"], name=hit["name"],
        part=hit["part"], start_line=hit["start_line"], end_line=hit["end_line"],
        text=hit["text"], breadcrumb=hit["breadcrumb"])
