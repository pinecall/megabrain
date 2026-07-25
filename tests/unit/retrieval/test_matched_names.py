"""`matched` names a few things, or it is not worth printing.

MEASURED on the compact render an agent actually receives. For "add a
redirect_back helper…" against sinatra, the whole map was 5 924 chars and
**2 700 of them — 45% — were the `matched:` lines**. One file, `base.rb`,
contributed 2 108 chars from THREE chunks.

The cause is that `matched_names` caps CHUNKS, not names, and a chunk's name is
not one name. Languages whose small siblings get packed into a single chunk
give that chunk a name listing everything inside it:

    "Sinatra.Helpers.cache_control, Sinatra.Helpers, Sinatra.Helpers.expires,
     Sinatra.Helpers, Sinatra.Helpers.last_modified, Sinatra.Helpers, …"

— a hundred entries with the container repeated between every one. It is also
REDUNDANT: the same symbols are printed underneath as the file's outline, which
is where a reader looks for them.

So the cap counts names, the container repeats are collapsed, and what survives
is what the word `matched` promises: the few names this file matched on.
"""

from __future__ import annotations

from megabrain.retrieval.bundle._related import matched_names
from megabrain.retrieval.params import DEFAULT_PARAMS
from megabrain.storage.model import ChunkMeta


def meta(name: str | None) -> ChunkMeta:
    return ChunkMeta(id=1, file="f.rb", kind="block", name=name, part=None,
                     start_line=1, end_line=9, text="", breadcrumb="f.rb")


def test_a_packed_chunk_does_not_spend_the_whole_budget() -> None:
    """The measured case: one chunk carrying a hundred names."""
    packed = ", ".join(f"App.Helpers.sym_{i}" for i in range(100))
    out = matched_names([meta(packed)], DEFAULT_PARAMS)
    assert len(out) <= DEFAULT_PARAMS.matched_names
    assert len(", ".join(out)) < 200, "still a wall of text"


def test_the_repeated_CONTAINER_is_collapsed() -> None:
    """`Sinatra.Helpers` appearing between every method is the packing
    artifact, not a match. Printed once it is context; printed fifty times it
    is what made the line unreadable."""
    name = "Sinatra.Helpers, Sinatra.Helpers.expires, Sinatra.Helpers, " \
           "Sinatra.Helpers.etag, Sinatra.Helpers"
    out = matched_names([meta(name)], DEFAULT_PARAMS)
    assert out.count("Sinatra.Helpers") <= 1
    assert "Sinatra.Helpers.expires" in out and "Sinatra.Helpers.etag" in out


def test_ORDER_is_preserved() -> None:
    """First-named is the best-scoring chunk's name. Sorting or set-ordering
    would put an arbitrary symbol in front of the one that actually matched."""
    out = matched_names([meta("alpha, beta"), meta("gamma")], DEFAULT_PARAMS)
    assert out == ["alpha", "beta", "gamma"]


def test_a_chunk_with_NO_name_contributes_nothing() -> None:
    assert matched_names([meta(None), meta("only")], DEFAULT_PARAMS) == ["only"]


def test_duplicates_across_chunks_appear_once() -> None:
    out = matched_names([meta("shared, one"), meta("shared, two")], DEFAULT_PARAMS)
    assert out == ["shared", "one", "two"]
