"""Incremental indexing: what survives a re-index and what must not.

The load-bearing case is `delete_file`. Re-indexing a file drops its OUTGOING
edges (they are rebuilt from the new source) but must KEEP its incoming ones:
the importers' A->B edges are still true, and deleting them silently destroyed
every edge whose source file happened to be processed before its destination in
the same pass. That failure is silent — the index still answers, just with
half its graph — so it is pinned here rather than described in a comment.
"""

from __future__ import annotations

import numpy as np
import pytest

from megabrain.storage import Store
from tests.unit.storage.factories import chunk, symbol


@pytest.fixture
def store(tmp_path: object) -> object:
    with Store(tmp_path) as s:      # type: ignore[arg-type]
        yield s


def test_an_unknown_file_has_no_sha(store: Store) -> None:
    assert store.files.sha("nope.py") is None


def test_upsert_then_read_back_the_sha(store: Store) -> None:
    store.files.upsert("a.py", "sha1", "skeleton", None)
    assert store.files.sha("a.py") == "sha1"


def test_reindex_keeps_incoming_edges(store: Store) -> None:
    """THE regression. b.py is re-indexed; a.py still imports it."""
    store.graph.replace_edges("a.py", [("b.py", "import")])
    store.graph.replace_edges("b.py", [("c.py", "import")])

    store.files.delete("b.py", drop_incoming=False)

    assert ("a.py", "b.py", "import") in store.graph.all_edges(), "incoming edge destroyed"
    assert ("b.py", "c.py", "import") not in store.graph.all_edges(), "outgoing edge survived"


def test_deleting_an_orphan_drops_incoming_edges_too(store: Store) -> None:
    """A file gone from disk has no valid importers left."""
    store.graph.replace_edges("a.py", [("b.py", "import")])
    store.files.delete("b.py", drop_incoming=True)
    assert store.graph.all_edges() == []


def test_delete_file_clears_chunks_and_symbols(store: Store) -> None:
    store.chunks.insert([chunk("a.py")], np.zeros((1, 4), dtype=np.float32))
    store.symbols.insert([symbol("a.py")])
    store.files.delete("a.py", drop_incoming=False)
    assert store.chunks.read_matrix()[0] == []
    assert store.symbols.read_for("a.py") == []


def test_all_paths_reflects_upserts(store: Store) -> None:
    store.files.upsert("a.py", "s", "", None)
    store.files.upsert("b/c.py", "s", "", None)
    assert store.files.all_paths() == {"a.py", "b/c.py"}


def test_paths_are_stored_verbatim_as_posix(store: Store) -> None:
    """Windows backslash keys corrupted the index once; POSIX everywhere is the
    fix, and the store must not silently normalise a caller's mistake."""
    store.files.upsert("src/pkg/mod.py", "s", "", None)
    assert store.files.sha("src/pkg/mod.py") == "s"
    assert store.files.sha("src\\pkg\\mod.py") is None
