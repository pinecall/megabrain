"""Turning named identifiers into RELATED entries — go-to-definition, in bulk.

MEASURED, and it is the finding that shaped this lane. Asked what sinatra's
early-exit mechanism was missing, a model named exactly the right identifiers:
`halt`, `pass`, `redirect`, `error`. Feeding those back through the EMBEDDER
found none of the ground truth, in any arrangement:

    query + terms, one search    CHANGELOG.md, cookie_tossing.rb, csp.rb
    terms only,    one search    referrer_policy.rb, xss_header.rb, …
    one search per term          25 files, none of them the answer

A bare identifier is a terrible sentence, and a sentence is what an embedding
space is built to place. The symbol table answers the same question exactly:
`halt` -> lib/sinatra/base.rb, one hit, the line it is defined on.

So the model names, and the SYMBOL TABLE resolves. A term it cannot resolve is
dropped rather than guessed at semantically — the arms above are what guessing
looks like, and a lane that only ever ADDS files cannot afford to add those.
"""

from __future__ import annotations

from ...contracts import Tier2File
from ...storage.model import ChunkMeta
from ..params import RetrievalParams
from ..state import SearchState
from ._convert import to_ref
from ._rank import Ranking
from ._related import related_entry

__all__ = ["term_entries", "MAX_FILES_PER_TERM", "TOO_AMBIGUOUS"]

MAX_FILES_PER_TERM = 3
TOO_AMBIGUOUS = 8
"""Definitions past which a name stops being a location.

`error` resolves to six files in sinatra and still points somewhere; a name
defined in forty is vocabulary, not an address, and admitting all of them
would bury the terms that did resolve.
"""


def term_entries(state: SearchState, terms: list[str], *, ranking: Ranking,
                 metas: list[ChunkMeta], params: RetrievalParams,
                 held: set[str]) -> list[Tier2File]:
    """RELATED entries for the files that DEFINE any of `terms`.

    Ordered by term, so a reader sees the first-named identifier's home first —
    the model names in the order it thinks, and that order is information.
    """
    entries: list[Tier2File] = []
    seen = set(held)
    for term in terms:
        for relpath, line in _definitions(state, term):
            if relpath in seen:
                continue
            seen.add(relpath)
            entries.append(_entry(state, relpath, line, ranking, metas, params))
    return entries


def _definitions(state: SearchState, term: str) -> list[tuple[str, int]]:
    """(file, line) per file defining `term`, best-first, or [] if it is not a
    symbol at all or is defined too widely to mean a place."""
    hits = state.store.symbols.find(term)
    if not hits or len({h["file"] for h in hits}) > TOO_AMBIGUOUS:
        return []
    first: dict[str, int] = {}
    for hit in hits:
        first.setdefault(str(hit["file"]), int(hit["line"]))
    return list(first.items())[:MAX_FILES_PER_TERM]


def _entry(state: SearchState, relpath: str, line: int, ranking: Ranking,
           metas: list[ChunkMeta], params: RetrievalParams) -> Tier2File:
    """The ordinary RELATED entry, pointed at the DEFINITION.

    Through `related_entry` so an expanded file looks exactly like every other
    file in the tier — it arrived differently, it does not read differently.
    What it does get is a better span: the file is here because it defines the
    identifier, so the chunk it opens at is the one holding that definition
    rather than whatever the query happened to match.
    """
    entry = related_entry(state, relpath, ranking, metas,
                          via_graph=False, params=params)
    # `state.metas` and not the scored ones: an expanded file is by definition
    # one the scoring never surfaced, so its chunks are absent from that list
    # and the span would come back empty for exactly the files this lane exists
    # to add.
    defining = _chunk_at(state.metas, relpath, line)
    if defining is not None:
        entry["best_chunk"] = to_ref(defining)
    return entry


def _chunk_at(metas: list[ChunkMeta], relpath: str, line: int) -> ChunkMeta | None:
    return next((m for m in metas
                 if m.file == relpath and m.start_line <= line <= m.end_line), None)
