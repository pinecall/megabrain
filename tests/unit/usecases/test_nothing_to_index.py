"""Pointing the engine at a repository it cannot read.

FOUND IN USE, and it was the worst possible version of the bug. A TypeScript
monorepo was registered, the studio selected it (it was first alphabetically),
`Re-index` was clicked with the mental map ticked, and the answer was:

    0 chunks · 0 edges · 0.41s · 0 cards written · 0 degraded

Every number true, nothing wrong reported, and no way to tell that from a
crash. This build reads `.py` and `.pyi`; that repository has 412 `.ts` files
and not one indexable file — and NOTHING said so, at any of the three places
that could have: the census, the index, or the summary.

So: the census counts what it walked past and could not read, by extension, and
indexing a repository with nothing to index is an ERROR that names the
extensions it found instead. An index of nothing answers nothing, and reporting
success about it is a lie that costs somebody an afternoon.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain._errors import NothingToIndex
from megabrain.usecases import build_index, scan
from tests.unit.indexing.fake import CountingEmbedder, write


@pytest.fixture
def unreadable(tmp_path: Path) -> Path:
    """A Swift/Kotlin project — languages this build has no grammar for yet.

    The fixture has moved TWICE, which is the point working as intended: it was
    TypeScript (the repository that provoked the check), then Java, and both are
    read now. The RULE has never changed — only the list of what is unclaimed.
    """
    write(tmp_path, {
        "ios/View.swift": "struct View {}\n",
        "ios/Model.swift": "struct Model {}\n",
        "android/Main.kt": "fun main() {}\n",
        "package.json": '{"name":"x"}\n',
    })
    return tmp_path


def test_the_census_names_what_it_CANNOT_read(unreadable: Path) -> None:
    """By extension and by count, so "why is this empty" is answered where the
    question is asked — before anything is indexed or paid for."""
    report = scan(unreadable)
    assert report["would_index"] == 0
    assert report["unsupported"][".swift"] == 2
    assert report["unsupported"][".kt"] == 1
    assert report["would_index"] == 0


def test_the_census_says_which_extensions_this_build_DOES_read(unreadable: Path) -> None:
    """The other half of the same answer. A list of what was rejected without a
    list of what is accepted leaves the reader guessing at the rule."""
    assert ".py" in scan(unreadable)["supported"]


def test_a_json_or_lockfile_is_not_reported_as_a_missing_language(
        unreadable: Path) -> None:
    """`package.json` is not a file anybody expects in a code index, and listing
    it as unsupported turns the finding into noise. What matters is the SOURCE
    this build cannot read."""
    assert ".json" not in scan(unreadable)["unsupported"]


def test_indexing_a_repo_with_nothing_readable_is_an_ERROR(unreadable: Path) -> None:
    with pytest.raises(NothingToIndex) as raised:
        build_index(unreadable, embedder=CountingEmbedder())
    message = str(raised.value)
    assert ".swift" in message and ".py" in message, \
        "it names what it found AND what it reads — either alone is a riddle"


def test_the_error_is_not_raised_when_there_is_something_to_index(
        unreadable: Path) -> None:
    """One readable file is a repository worth indexing. The check is about
    nothing being readable, not about everything being readable."""
    write(unreadable, {"tool.py": "def go():\n    return 1\n"})
    report = build_index(unreadable, embedder=CountingEmbedder())
    assert report["files"] == 1


def test_an_UNCHANGED_reindex_of_a_real_repo_is_never_the_error(
        unreadable: Path) -> None:
    """The two must not be confused: "nothing changed" is success and "nothing
    readable" is a failure, and they produce the same zeros in the delta."""
    write(unreadable, {"tool.py": "def go():\n    return 1\n"})
    build_index(unreadable, embedder=CountingEmbedder())
    again = build_index(unreadable, embedder=CountingEmbedder())
    assert again["changed"] == 0 and int(again["total_chunks"]) > 0


def test_an_empty_directory_says_the_same_thing(tmp_path: Path) -> None:
    """Nothing found at all is the same failure with an empty list, not a
    different code path that reports success."""
    with pytest.raises(NothingToIndex):
        build_index(tmp_path, embedder=CountingEmbedder())
