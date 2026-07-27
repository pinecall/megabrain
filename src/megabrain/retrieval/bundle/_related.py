"""Rendering a RELATED file as a MAP rather than as code.

File, best span, the names that matched, an outline, the first docstring found.
Enough to decide whether to open it, at a fraction of what full bodies cost —
and the decision belongs to whoever is reading, not to the ranker.
"""

from __future__ import annotations

from ...contracts import Tier2File
from ...storage.model import ChunkMeta
from ...storage.rows import SymbolRow
from ..params import RetrievalParams
from ..state import SearchState
from ._convert import OUTLINE_KINDS, to_outline, to_ref
from ._rank import Ranking

__all__ = ["neighbours_of", "related_entry", "matched_names"]


def matched_names(hits: list[ChunkMeta], params: RetrievalParams) -> list[str]:
    """The few names this file matched on — capped by NAME, not by chunk.

    A chunk's name is not one name. Where a language's small siblings get
    packed into a single chunk, that chunk is named for everything inside it,
    with the container repeated between every member:

        "Sinatra.Helpers.cache_control, Sinatra.Helpers, Sinatra.Helpers.expires, …"

    Capping chunks let ONE of those spend the whole line. Measured on the map
    an agent receives: 2 700 of 5 924 chars — 45% of the render — were these
    lines, and `base.rb` alone contributed 2 108 from three chunks. The same
    symbols are printed below as the file's outline, so the wall was redundant
    as well as unreadable.
    """
    seen: dict[str, None] = {}
    for meta in hits:
        for name in (meta.name or "").split(","):
            if (name := name.strip()):
                seen.setdefault(name, None)
    return list(seen)[:params.matched_names]


def related_entry(state: SearchState, relpath: str, ranking: Ranking,
                  metas: list[ChunkMeta], *, via_graph: bool,
                  params: RetrievalParams) -> Tier2File:
    indexes = ranking.chunks_of.get(relpath, [])
    symbols = state.store.symbols.read_for(relpath)
    return Tier2File(
        file=relpath,
        score=ranking.best_of.get(relpath, 0.0),
        via_graph=via_graph,
        matched=matched_names([metas[i] for i in indexes], params),
        doc=_first_doc(symbols),
        best_chunk=to_ref(metas[indexes[0]]) if indexes else None,
        symbols=[to_outline(s) for s in symbols
                 if s["kind"] in OUTLINE_KINDS][:params.outline_symbols],
    )


def _first_doc(symbols: list[SymbolRow]) -> str | None:
    """The file's first docstring line — a one-line answer to "what is this",
    which is most of what a map entry is for."""
    return next((s["doc"] for s in symbols
                 if isinstance(s.get("doc"), str)), None)      # type: ignore[return-value]


def neighbours_of(state: SearchState, candidates: list[str], ranking: Ranking,
                  params: RetrievalParams) -> list[str]:
    """Graph neighbours of the strongest few files.

    Only the top three seed this: an import edge is evidence about the file it
    came from, and past the leaders that evidence is about something the query
    barely matched. Neighbours are ordered by their OWN score — the graph
    supplies candidates, it never ranks.

    The tie-break on the path is what makes that order TOTAL. The candidates
    come out of a set, whose iteration order comes from salted string hashes,
    so sorting on the score alone left equally-scoring neighbours in a
    different order in every process — a different bundle for the same query
    and the same index.
    """
    reachable: set[str] = set()
    for relpath in candidates[:3]:
        reachable |= state.store.graph.neighbors(relpath)
    reachable -= set(candidates)
    scored = reachable & set(ranking.order)
    return sorted(scored, key=lambda f: (-ranking.best_of[f], f))[:params.graph_extras]
