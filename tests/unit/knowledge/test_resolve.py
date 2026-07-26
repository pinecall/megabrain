"""Naming a node: a term, not a path.

Nobody types `src/megabrain/retrieval/scoring/lanes.py` into a graph. They type
`lanes`, or `the scoring pipeline`. So the term is resolved in the order the
answer is most certain: the exact path, then a filename tail, and only then by
MEANING against the file skeletons retrieval already embedded.

Test files carry the same soft down-weight retrieval applies, because a test's
skeleton is full of the vocabulary of the thing it tests — raw cosine sends
"the studio web server" to its test file. They stay reachable: name one and the
path match wins before anything is embedded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.knowledge.symbols.resolve import resolve_node
from megabrain.storage import Store
from megabrain.usecases import build_index
from tests.unit.indexing.fake import CountingEmbedder, write
from tests.unit.knowledge.fake import WordEmbedder

FILES = {
    "src/serve.py": "def serve_studio_web_server(port):\n    return port\n",
    "tests/test_serve.py": "def test_serve_studio_web_server():\n    assert True\n",
    "src/scoring/lanes.py": "def fuse(vector, lexical):\n    return vector\n",
    "docs/lanes.md": "# lanes\n",
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, FILES)
    build_index(tmp_path, embedder=WordEmbedder())
    return tmp_path


def resolved(repo: Path, term: str) -> str | None:
    """The SAME embedder that built the index answers the query — a term and a
    skeleton compared through two different models is not a comparison."""
    with Store(repo) as store:
        return resolve_node(store, sorted(store.files.all_paths()), term,
                            embedder=WordEmbedder())


def test_an_exact_path_resolves_to_itself(repo: Path) -> None:
    assert resolved(repo, "src/scoring/lanes.py") == "src/scoring/lanes.py"


def test_a_leading_slash_is_forgiven(repo: Path) -> None:
    """People paste paths. A leading slash is a typing artefact, not a
    different file, and rejecting it sends a certain answer down the guessing
    path for no reason."""
    assert resolved(repo, "/src/scoring/lanes.py") == "src/scoring/lanes.py"


def test_a_bare_filename_resolves_by_tail(repo: Path) -> None:
    assert resolved(repo, "lanes.py") == "src/scoring/lanes.py"


def test_a_tail_match_beats_the_embedding(repo: Path) -> None:
    """A named file is not a question. Certainty first: any embedding-based
    guess here would be a worse answer arrived at more expensively."""
    assert resolved(repo, "serve.py") == "src/serve.py"


def test_an_ambiguous_tail_resolves_DETERMINISTICALLY(repo: Path) -> None:
    """`lanes` names two files. Picking by iteration order means the same term
    resolves differently between runs, so the tie breaks on the sorted path."""
    assert resolved(repo, "lanes") == resolved(repo, "lanes")
    assert resolved(repo, "lanes") in {"docs/lanes.md", "src/scoring/lanes.py"}


def test_a_term_that_names_nothing_resolves_by_MEANING(repo: Path) -> None:
    """The point of the whole ladder: "the scoring pipeline" is not a path and
    still has an answer."""
    assert resolved(repo, "fuse vector lexical scoring") == "src/scoring/lanes.py"


def test_a_test_file_does_not_win_on_its_subjects_vocabulary(repo: Path) -> None:
    """`tests/test_serve.py` contains every word of the query. It is still the
    wrong answer to "the studio web server", and the penalty is what keeps it
    from winning."""
    assert resolved(repo, "serve studio web server") == "src/serve.py"


def test_naming_a_test_file_still_reaches_it(repo: Path) -> None:
    """The down-weight is a tiebreak, not a ban."""
    assert resolved(repo, "test_serve.py") == "tests/test_serve.py"


def test_an_empty_index_resolves_to_nothing(tmp_path: Path) -> None:
    write(tmp_path, {"a.py": "x = 1\n"})
    build_index(tmp_path, embedder=CountingEmbedder())
    with Store(tmp_path) as store:
        assert resolve_node(store, [], "anything") is None
