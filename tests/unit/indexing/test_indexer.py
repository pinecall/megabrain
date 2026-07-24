"""The indexing pipeline: chunk everything, embed ONCE, then write.

The phase order is the load-bearing part. Embedding per file turns a cold index
into two HTTP round trips per changed file — a file's few chunks never fill a
batch, and its skeleton goes out as a request of one — which is minutes of
sequential waiting on a large repository. Chunking is pure CPU, so it all
happens first and the network is touched exactly once.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.indexing.indexer import index_repo
from megabrain.storage import Store
from tests.unit.indexing.fake import CountingEmbedder, write


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, {"a.py": "def a(): pass\n", "b.py": "def b(): pass\n"})
    return tmp_path


def test_a_cold_index_embeds_in_one_call(repo: Path) -> None:
    """Two files, one request. This is the whole reason for the phase split."""
    embedder = CountingEmbedder()
    stats = index_repo(repo, embedder=embedder)
    assert embedder.calls == 1
    assert stats["files"] == 2 and stats["changed"] == 2


def test_chunks_and_skeletons_share_the_batch(repo: Path) -> None:
    """A skeleton sent on its own is a request of one text. They travel with
    the chunks and get sliced back apart after."""
    embedder = CountingEmbedder()
    index_repo(repo, embedder=embedder)
    assert embedder.texts > 2, "skeletons were not batched with the chunks"


def test_an_unchanged_file_is_not_re_embedded(repo: Path) -> None:
    index_repo(repo, embedder=CountingEmbedder())
    second = CountingEmbedder()
    stats = index_repo(repo, embedder=second)
    assert stats["changed"] == 0 and stats["unchanged"] == 2
    assert second.calls == 0, "nothing changed, so nothing should be embedded"


def test_only_the_changed_file_is_re_embedded(repo: Path) -> None:
    index_repo(repo, embedder=CountingEmbedder())
    (repo / "a.py").write_text("def a(): return 1\n", encoding="utf-8")
    second = CountingEmbedder()
    stats = index_repo(repo, embedder=second)
    assert stats["changed"] == 1 and stats["unchanged"] == 1
    assert second.calls == 1


def test_force_re_embeds_everything(repo: Path) -> None:
    index_repo(repo, embedder=CountingEmbedder())
    stats = index_repo(repo, embedder=CountingEmbedder(), force=True)
    assert stats["changed"] == 2


def test_a_deleted_file_is_pruned(repo: Path) -> None:
    index_repo(repo, embedder=CountingEmbedder())
    (repo / "a.py").unlink()
    stats = index_repo(repo, embedder=CountingEmbedder())
    assert stats["removed"] == 1
    with Store(repo) as store:
        assert store.files.all_paths() == {"b.py"}


def test_a_failed_embed_writes_nothing(repo: Path) -> None:
    """The whole pass aborts BEFORE any row is written, so a network failure
    leaves the previous index intact rather than half-replaced."""
    class Failing(CountingEmbedder):
        def embed(self, texts, *, on_batch=None):        # type: ignore[no-untyped-def]
            raise RuntimeError("upstream down")

    with pytest.raises(RuntimeError):
        index_repo(repo, embedder=Failing())
    with Store(repo) as store:
        assert store.files.all_paths() == set()


def test_progress_reports_files_then_embedding(repo: Path) -> None:
    """Indexing a large repository is a long silence otherwise."""
    seen: list[str] = []
    index_repo(repo, embedder=CountingEmbedder(), on_progress=lambda e: seen.append(e["type"]))
    assert "file" in seen and "embed" in seen


def test_stats_report_what_the_pass_actually_did(repo: Path) -> None:
    stats = index_repo(repo, embedder=CountingEmbedder())
    assert stats["chunks"] > 0
    assert stats["partition_violations"] == 0
    assert stats["seconds"] >= 0
