"""Indexing findings from the audit round.

The pipeline's failures are all of one kind: it reports what it INTENDED, and
the index quietly holds something else — rows for a file that was never read,
a marker for a graph that was never built, vectors filed against the wrong text.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from megabrain.indexing.discover import MAX_FILE_BYTES
from megabrain.indexing.indexer import index_repo
from megabrain.storage import Store
from tests.unit.indexing.fake import CountingEmbedder, write


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return write(tmp_path, {"a.py": "def a(): pass\n", "b.py": "import a\n"})


def test_a_skipped_file_keeps_the_edges_pointing_at_it(repo: Path) -> None:
    """A file skipped this pass is still ON DISK, so it is not an orphan.

    Pruning it as one deletes the edges pointing AT it — edges belonging to
    other files, which are still perfectly true. The import graph loses arcs
    because one unrelated file grew past the size limit.
    """
    index_repo(repo, embedder=CountingEmbedder())
    with Store(repo) as store:
        store.graph.replace_edges("b.py", [("a.py", "import")])

    (repo / "a.py").write_text("x = 1\n" * MAX_FILE_BYTES, encoding="utf-8")
    index_repo(repo, embedder=CountingEmbedder())

    with Store(repo) as store:
        assert store.graph.neighbors("b.py") == {"a.py"}, \
            "a skipped file was pruned as an orphan and took its incoming edges"


def test_a_pass_with_nothing_to_graph_does_not_claim_an_edge_schema(
        tmp_path: Path) -> None:
    """The marker means "the edges in this index were built by schema N".

    Stamping it after a pass that examined nothing makes every future pass
    believe the graph is current, so the rebuild the marker exists to trigger
    never happens. Here no strategy claims the file, so the edge pass has no
    target — and says so by not stamping.
    """
    write(tmp_path, {"notes.md": "# not a language this registry knows\n"})
    index_repo(tmp_path, embedder=CountingEmbedder())

    with Store(tmp_path) as store:
        assert store.graph.get_meta("edge_schema") is None
        assert store.graph.all_edges() == []


def test_switching_embedding_model_re_embeds_the_whole_index(repo: Path) -> None:
    """Two models are two vector spaces. A mixed index does not fail — it
    ranks nonsense against the new query, which no assertion downstream sees."""
    index_repo(repo, embedder=CountingEmbedder())

    other = CountingEmbedder()
    other.model = "different-embed"
    stats = index_repo(repo, embedder=other)

    assert stats["changed"] == 2, "a model swap left the old vectors in place"


def test_the_same_model_on_a_second_pass_does_not_force_a_re_embed(repo: Path) -> None:
    """The other half: the force must come from a CHANGE, not from the marker
    merely being present."""
    index_repo(repo, embedder=CountingEmbedder())
    assert index_repo(repo, embedder=CountingEmbedder())["changed"] == 0


def test_an_embedder_returning_too_few_vectors_is_caught(repo: Path) -> None:
    """The batch is sliced back apart POSITIONALLY, so a short reply shifts
    every file after the gap onto vectors computed for other text."""
    class Short(CountingEmbedder):
        def embed(self, texts, *, on_batch=None):            # type: ignore[no-untyped-def]
            return super().embed(texts, on_batch=on_batch)[:-1]

    with pytest.raises(ValueError, match="vectors for"):
        index_repo(repo, embedder=Short())


def test_the_fake_embedder_is_stable_across_processes() -> None:
    """`hash()` on a str is salted per process, so vectors built from it differ
    between runs — a fixture that claims to be deterministic and is not turns
    any cross-process comparison into a coin flip."""
    code = ("from tests.unit.indexing.fake import CountingEmbedder;"
            "print(CountingEmbedder().embed(['x'])[0].tolist())")
    runs = {subprocess.run([sys.executable, "-c", code], check=True, text=True,
                           capture_output=True, cwd=str(Path(__file__).parents[3])).stdout
            for _ in range(2)}
    assert len(runs) == 1, "the same text embedded differently in two processes"
