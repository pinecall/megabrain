"""The use-case layer: what every transport calls.

Thin on purpose, but not empty. It owns the two things a transport must not
each solve its own way — finding the index a path belongs to, and deciding
policy the engine deliberately refuses to decide.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain._errors import IndexNotFound
from megabrain.usecases import build_index, resolve_root, search
from tests.unit.indexing.fake import CountingEmbedder, write


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, {"a.py": "import b\ndef alpha(): pass\n",
                     "b.py": "def run(): pass\n",
                     "sub/c.py": "def gamma(): pass\n"})
    build_index(tmp_path, embedder=CountingEmbedder())
    return tmp_path


def test_the_root_is_found_from_a_subdirectory(repo: Path) -> None:
    """`megabrain search` typed three directories deep must answer for the
    repository, the way git does — nobody runs tools from the root."""
    assert resolve_root(repo / "sub") == repo


def test_the_root_is_found_from_a_file_inside_the_repo(repo: Path) -> None:
    assert resolve_root(repo / "sub" / "c.py") == repo


def test_a_path_with_no_index_above_it_says_what_to_run(tmp_path: Path) -> None:
    """The error is the only thing a first-time user sees, so it names the
    command that fixes it rather than reporting a missing file."""
    with pytest.raises(IndexNotFound, match="megabrain index"):
        resolve_root(tmp_path)


def test_searching_from_a_subdirectory_answers_for_the_whole_repo(repo: Path) -> None:
    bundle = search(repo / "sub", "alpha", embedder=CountingEmbedder())
    assert bundle["repo"] == repo.name
    assert bundle["tier1"], "nothing came back from a repo that has matches"


def test_indexing_a_path_that_is_not_there_fails_loudly(tmp_path: Path) -> None:
    """A walk of a missing path yields nothing, so this REPORTED SUCCESS —
    "0 files, 0 chunks" — and left an empty index beside the typo. Every later
    query then answered nothing, correctly, about a repo nobody indexed."""
    with pytest.raises(NotADirectoryError, match="not a directory"):
        build_index(tmp_path / "typo", embedder=CountingEmbedder())


def test_the_report_says_what_the_pass_did(repo: Path) -> None:
    report = build_index(repo, embedder=CountingEmbedder())
    assert report["files"] == 3
    assert report["changed"] == 0 and report["unchanged"] == 3
    assert report["seconds"] >= 0


def test_a_second_index_of_the_same_tree_costs_no_embedding(repo: Path) -> None:
    embedder = CountingEmbedder()
    build_index(repo, embedder=embedder)
    assert embedder.calls == 0
