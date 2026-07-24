"""Storage round-trips: what goes in comes back, with the vectors aligned.

`load_matrix` is the hot path — it feeds the numpy matrix every query scores
against — so the invariant that matters is ALIGNMENT: row *i* of the matrix
must belong to metas[i]. A silent misalignment does not raise; it just returns
confidently wrong answers.
"""

from __future__ import annotations

import numpy as np
import pytest

from megabrain.storage import Store
from tests.unit.storage.factories import chunk, symbol, vectors


@pytest.fixture
def store(tmp_path: object) -> object:
    with Store(tmp_path) as s:      # type: ignore[arg-type]
        yield s


def test_chunks_round_trip_with_aligned_vectors(store: Store) -> None:
    chunks = [chunk("a.py", cid=0, start=1, end=5), chunk("b.py", cid=1, start=1, end=9)]
    vecs = vectors([[1.0, 0.0], [0.0, 1.0]])
    store.chunks.insert(chunks, vecs)

    metas, matrix = store.chunks.read_matrix()

    assert [m.file for m in metas] == ["a.py", "b.py"]
    assert matrix.shape == (2, 2)
    for i, meta in enumerate(metas):
        expected = vecs[0] if meta.file == "a.py" else vecs[1]
        assert np.allclose(matrix[i], expected), "row/meta misalignment"


def test_a_chunk_without_a_vector_never_reaches_the_matrix(store: Store) -> None:
    """An unembedded chunk would shift every later row by one."""
    store.chunks.insert([chunk("a.py")], None)
    metas, matrix = store.chunks.read_matrix()
    assert metas == [] and matrix.shape[0] == 0


def test_empty_index_yields_an_empty_matrix_not_a_crash(store: Store) -> None:
    metas, matrix = store.chunks.read_matrix()
    assert metas == [] and matrix.shape[0] == 0


def test_symbols_round_trip_in_line_order(store: Store) -> None:
    store.symbols.insert([symbol("a.py", name="z", line=9), symbol("a.py", name="a", line=1)])
    assert [s["name"] for s in store.symbols.read_for("a.py")] == ["a", "z"]


def test_decorators_survive_as_a_list(store: Store) -> None:
    """Serialisation policy is the store's knowledge; callers see a list."""
    store.symbols.insert([symbol("a.py", decorators=("property", "cached"))])
    assert store.symbols.read_for("a.py")[0]["decorators"] == ["property", "cached"]


def test_meta_round_trips_structured_values(store: Store) -> None:
    store.graph.set_meta("last_index", {"t": 1.5, "files": 3})
    assert store.graph.get_meta("last_index") == {"t": 1.5, "files": 3}
    assert store.graph.get_meta("absent") is None


def test_edges_are_deduplicated_per_source(store: Store) -> None:
    store.graph.replace_edges("a.py", [("b.py", "import"), ("b.py", "import")])
    assert store.graph.all_edges() == [("a.py", "b.py", "import")]


def test_neighbors_are_bidirectional(store: Store) -> None:
    """The graph supplies candidates in both directions: who I import, and who
    imports me. It never ranks — that is hard rule #3."""
    store.graph.replace_edges("a.py", [("b.py", "import")])
    store.graph.replace_edges("c.py", [("a.py", "call")])
    assert store.graph.neighbors("a.py") == {"b.py", "c.py"}
