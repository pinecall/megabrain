"""Rendering the lexical anchor floor's picks as spans.

The span is what makes an anchor actionable: the reader opens exactly the
lines holding the identifier they asked about, instead of a whole file.
"""

from __future__ import annotations

from ..._arrays import Matrix
from ...contracts import AnchorHit
from ...storage.model import ChunkMeta
from ..params import RetrievalParams
from .floors import anchor_chunks

__all__ = ["render_anchors"]


def render_anchors(query: str, metas: list[ChunkMeta], fused: Matrix,
                   params: RetrievalParams) -> list[AnchorHit]:
    """Chunks the lexical floor pulled in, as spans rather than bodies."""
    return [AnchorHit(file=metas[i].file, start_line=metas[i].start_line,
                      end_line=metas[i].end_line, terms=terms)
            for i, terms in anchor_chunks(query, metas, fused, params).items()]
