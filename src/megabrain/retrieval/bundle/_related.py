"""Rendering a RELATED file as a MAP rather than as code.

File, best span, the names that matched, an outline, the first docstring found.
Enough to decide whether to open it, at a fraction of what full bodies cost —
and the decision belongs to whoever is reading, not to the ranker.
"""

from __future__ import annotations

from ...contracts import Tier2File
from ...storage.model import ChunkMeta
from .._render import OUTLINE_KINDS, to_outline, to_ref
from ..params import RetrievalParams
from ..state import SearchState
from ._rank import Ranking

__all__ = ["related_entry"]


def related_entry(state: SearchState, relpath: str, ranking: Ranking,
                  metas: list[ChunkMeta], *, via_graph: bool,
                  params: RetrievalParams) -> Tier2File:
    indexes = ranking.chunks_of.get(relpath, [])
    symbols = state.store.symbols.read_for(relpath)
    return Tier2File(
        file=relpath,
        score=ranking.best_of.get(relpath, 0.0),
        via_graph=via_graph,
        matched=[name for i in indexes[:params.matched_names]
                 if (name := metas[i].name)],
        doc=_first_doc(symbols),
        best_chunk=to_ref(metas[indexes[0]]) if indexes else None,
        symbols=[to_outline(s) for s in symbols
                 if s["kind"] in OUTLINE_KINDS][:params.outline_symbols],
    )


def _first_doc(symbols: list[dict[str, object]]) -> str | None:
    """The file's first docstring line — a one-line answer to "what is this",
    which is most of what a map entry is for."""
    return next((s["doc"] for s in symbols
                 if isinstance(s.get("doc"), str)), None)      # type: ignore[return-value]
