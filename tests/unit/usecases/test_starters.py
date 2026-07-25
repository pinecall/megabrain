"""Starter questions, and where they come from.

FOUND IN USE: "no carga las queries configuradas por proyecto, siempre muestras
las mismas". Measured across every registered repository — **not one declares a
query** — so the strip that was supposed to show a repo's own questions showed
nothing, and the only constant text on screen was the input's placeholder. It
read as "the same suggestions forever" because it was never per-repo at all.

v2 had a fallback this port dropped: when a repository declares nothing, derive
starters FROM THE INDEX — no model, no network. And it labelled the source, so
"the repo asked for this" and "we guessed from the graph" never looked alike.

The derivation is deliberately dull. It names the repository's most depended-on
files and its most connected symbols, because those are the two questions a
newcomer to any codebase actually has, and both are facts the index already
holds.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megabrain.project import CONFIG_FILE
from megabrain.usecases import build_index
from megabrain.usecases.starters import starters_for
from tests.unit.indexing.fake import CountingEmbedder, write

FILES = {
    "core/models.py": "class Model:\n    def dump(self):\n        return 1\n",
    "core/client.py": "from .models import Model\n\n\n"
                      "class Client:\n    def send(self, m: Model):\n        return m\n",
    "api/routes.py": "from ..core.client import Client\nfrom ..core.models import Model\n\n\n"
                     "def handle(c: Client):\n    return c.send(Model())\n",
    "tests/test_client.py": "def test_send():\n    assert True\n",
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, FILES)
    build_index(tmp_path, embedder=CountingEmbedder())
    return tmp_path


def test_a_repo_that_declares_queries_gets_ITS_OWN(repo: Path) -> None:
    """The whole point of the config file: the repository's own words win."""
    (repo / CONFIG_FILE).write_text(json.dumps(
        {"queries": ["how does the retry lane work?", "where is auth checked?"]}),
        encoding="utf-8")
    found = starters_for(repo)
    assert found["source"] == "file"
    assert found["queries"][0] == "how does the retry lane work?"


def test_a_repo_that_declares_NOTHING_still_gets_starters(repo: Path) -> None:
    """The dropped fallback. An empty strip taught the reader that the feature
    does not work, which is worse than a plainly-labelled guess."""
    found = starters_for(repo)
    assert found["source"] == "derived"
    assert found["queries"], "a repository with an index can always be asked something"


def test_the_derived_questions_name_the_repos_OWN_files(repo: Path) -> None:
    """Derived from the graph, so they have to mention what this repository is
    made of — generic questions would be the same for every repo, which is the
    complaint this fixes."""
    text = " ".join(starters_for(repo)["queries"])
    assert "models.py" in text or "client.py" in text or "Model" in text


def test_TESTS_are_not_what_a_newcomer_is_pointed_at(repo: Path) -> None:
    """A test file is high-degree by design; leading with it answers the wrong
    question first."""
    assert "test_client" not in " ".join(starters_for(repo)["queries"])


def test_the_derived_list_is_DETERMINISTIC(repo: Path) -> None:
    """Suggestions that reshuffle per reload look broken, and hide whether the
    strip is even reacting to the repository."""
    assert starters_for(repo)["queries"] == starters_for(repo)["queries"]


def test_an_empty_index_derives_nothing_rather_than_inventing(tmp_path: Path) -> None:
    """No index, no facts, no questions. A placeholder question about a
    repository nobody indexed is the confident-nonsense failure again."""
    from megabrain.storage import Store

    with Store(tmp_path):
        pass
    found = starters_for(tmp_path)
    assert found["queries"] == [] and found["source"] == "none"


def test_the_source_is_reported_so_the_UI_can_be_honest(repo: Path) -> None:
    assert starters_for(repo)["source"] in ("file", "derived", "none")
