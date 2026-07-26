"""What CARRIES a hop.

A route of filenames is a claim without evidence. The question a reader has at
every hop is "connected through WHAT" — which function, and where is it called.

The rule that makes the answer trustworthy is that a use is verified by the
AST, receiver included. Word-matching a symbol name finds it in a comment, in a
string, in an unrelated method of the same name; and an attribute call whose
receiver resolves somewhere else is not a use at all — `re.search(...)` once
"connected" the reranker to the bundle's own `search()`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.knowledge.routes.carriers import hop_code, hop_symbols
from megabrain.storage import Store
from megabrain.usecases import build_index
from tests.unit.indexing.fake import CountingEmbedder, write

SCORING = """\
from .narrator import narrate


def fuse(hits):
    text = narrate(hits)
    return text
"""

NARRATOR = """\
def narrate(hits):
    \"\"\"Turn hits into prose.\"\"\"
    return " ".join(str(h) for h in hits)


def unused_helper():
    return None
"""

DECOY = """\
import re


def scan(source):
    # narrate is mentioned here in a comment, and in a string below
    return re.search(r"narrate", source)
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, {"scoring.py": SCORING, "narrator.py": NARRATOR,
                     "decoy.py": DECOY, "__init__.py": ""})
    build_index(tmp_path, embedder=CountingEmbedder())
    return tmp_path


def carriers(repo: Path, one: str, two: str) -> list[str]:
    with Store(repo) as store:
        return hop_symbols(store, repo, one, two)


def test_the_carrier_is_the_symbol_defined_on_one_side_and_used_on_the_other(
        repo: Path) -> None:
    assert carriers(repo, "scoring.py", "narrator.py")[:1] == ["narrate"]


def test_the_direction_of_the_walk_does_not_matter(repo: Path) -> None:
    """The graph is undirected, so a hop arrives from either side and the
    carrier has to be found in both directions."""
    assert carriers(repo, "narrator.py", "scoring.py")[:1] == ["narrate"]


def test_a_symbol_that_is_merely_MENTIONED_is_not_a_carrier(repo: Path) -> None:
    """`decoy.py` contains the string "narrate" twice — in a comment and in a
    regex — and calls it never. A word-boundary scan reports a connection here;
    the AST reports none, which is the truth."""
    assert carriers(repo, "decoy.py", "narrator.py") == []


def test_an_attribute_call_to_ANOTHER_module_is_not_a_carrier(repo: Path) -> None:
    """`decoy.scan` calls `re.search`. The bundle defines a `search` too, and
    the receiver is what tells them apart: `re` resolves outside the repository,
    so the call cannot carry an in-repo hop."""
    write(repo, {"bundle.py": "def search(q):\n    return q\n"})
    build_index(repo, embedder=CountingEmbedder())
    assert "search" not in carriers(repo, "decoy.py", "bundle.py")


def test_a_short_name_is_not_a_carrier(repo: Path) -> None:
    """One- and two-letter names collide with everything. The evidence they
    give is worth less than the noise they add."""
    write(repo, {"tiny.py": "def go():\n    return 1\n",
                 "user.py": "from .tiny import go\n\n\ndef run():\n    return go()\n"})
    build_index(repo, embedder=CountingEmbedder())
    assert "go" not in carriers(repo, "user.py", "tiny.py")


def test_the_hop_carries_REAL_code_from_both_sides(repo: Path) -> None:
    """The use site and the definition. Two snippets, because "who calls it"
    and "what it does" are the two halves of understanding a hop, and neither
    one alone lets a reader continue."""
    with Store(repo) as store:
        code = hop_code(store, repo, "scoring.py", "narrator.py",
                        ["narrate"])
    assert code is not None
    assert code["symbol"] == "narrate" and code["verified"] is True
    use, definition = code["use"], code["definition"]
    assert use is not None and definition is not None
    assert use["file"] == "scoring.py" and "narrate(hits)" in use["text"]
    assert definition["file"] == "narrator.py"
    assert "def narrate(hits):" in definition["text"]


def test_the_use_site_names_the_function_it_sits_IN(repo: Path) -> None:
    """A call site means nothing without knowing whose body it is in: that is
    the connective tissue of the whole story — `fuse` calls `narrate`."""
    with Store(repo) as store:
        code = hop_code(store, repo, "scoring.py", "narrator.py", ["narrate"])
    assert code is not None and (code["use"] or {})["in_symbol"] == "fuse"


def test_the_highlighted_rows_are_the_ACTUAL_call_lines(repo: Path) -> None:
    """The studio marks these rows. Marking the first word match instead would
    highlight the import line, or a same-named local, and quietly teach the
    reader something false."""
    with Store(repo) as store:
        code = hop_code(store, repo, "scoring.py", "narrator.py", ["narrate"])
    use = (code or {})["use"]
    assert use is not None
    lines = use["text"].splitlines()
    marked = [lines[row] for row in use["hi_rows"]]
    assert any("narrate(hits)" in line for line in marked)


def test_a_hop_with_no_verifiable_carrier_returns_nothing(repo: Path) -> None:
    """Not a guess. A hop whose carrier cannot be shown says so, and the route
    still renders — the filenames were never in doubt."""
    with Store(repo) as store:
        assert hop_code(store, repo, "decoy.py", "narrator.py", []) is None


def test_carriers_are_capped_and_ordered_by_evidence(repo: Path) -> None:
    """A hop between two big files can share a dozen names. The list is for
    reading, so it is short, and the strongest evidence comes first."""
    body = "".join("from .narrator import narrate\n" for _ in range(1))
    calls = "\n".join(f"    narrate({n})" for n in range(3))
    write(repo, {"heavy.py": f"{body}\n\ndef run():\n{calls}\n"})
    build_index(repo, embedder=CountingEmbedder())
    found = carriers(repo, "heavy.py", "narrator.py")
    assert found[0] == "narrate" and len(found) <= 4
