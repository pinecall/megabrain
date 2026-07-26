"""The imports of a test file the change writes in — read from the CITATIONS.

MEASURED twice. First: handed a correct surface, an agent still grepped and
read the test file twice to learn whether the symbol it needed was already
imported. Second, after the preamble existed: it VANISHED, because it was
computed from the prepared edit operations and one of those was dropped — its
anchor was a blank line — so the agent guessed the imports instead. It guessed
right, and said so: a `NameError` would have cost a Read and a second edit.

A cited test file is a test file the reader is about to write in. That is the
relation, and it does not depend on any operation surviving.
"""

from __future__ import annotations

from megabrain.ask._headers import already_imported
from megabrain.chunkers.model import Chunk, Symbol
from megabrain.storage import Store

PREAMBLE = ("import pytest\nfrom app import thing\n\nneeds_v2 = pytest.mark.skipif(\n"
            "    not HAS_V2, reason='needs v2')\n\n\ndef test_one():\n    pass")


def repo(tmp_path) -> Store:
    store = Store(tmp_path)
    for path in ("tests/test_app.py", "lib/app.py"):
        store.files.upsert(path, "sha", "", None)
    store.symbols.insert([
        Symbol(file="tests/test_app.py", name="test_one", kind="function", line=8,
               end_line=9, signature=None, decorators=(), doc=None),
        Symbol(file="lib/app.py", name="thing", kind="function", line=2,
               end_line=3, signature=None, decorators=(), doc=None),
    ])
    store.chunks.insert([
        Chunk(file="tests/test_app.py", kind="module", name=None, part=None,
              start_line=1, end_line=9, text=PREAMBLE, breadcrumb="t"),
        Chunk(file="lib/app.py", kind="function", name="thing", part=None,
              start_line=1, end_line=3, text="x = 1\ndef thing():\n    pass",
              breadcrumb="a"),
    ], None)
    return store


def test_a_cited_test_file_gets_its_PREAMBLE(tmp_path) -> None:
    """Everything above the first declaration: the imports and the skip marker
    the reader has to spell the same way."""
    with repo(tmp_path) as store:
        out = already_imported(store, "[[tests/test_app.py:20-30]]")
    assert "[[tests/test_app.py:1-7]]" in out


def test_the_preamble_does_not_depend_on_an_OPERATION(tmp_path) -> None:
    """The measured regression. The surface cites the test file as a sibling to
    imitate and nothing else — no anchor, no edit — and the reader still needs
    to know what is in scope."""
    with repo(tmp_path) as store:
        out = already_imported(store, "Imitate this:\n[[tests/test_app.py:8-9]]")
    assert "what is already imported" in out


def test_a_PRODUCTION_file_gets_no_preamble(tmp_path) -> None:
    """Production code is reached through the symbols the map lists; only a
    test is written by imitating the file around it."""
    with repo(tmp_path) as store:
        assert already_imported(store, "[[lib/app.py:1-3]]") == ""


def test_a_file_declaring_on_line_ONE_has_no_preamble(tmp_path) -> None:
    """There is nothing above line 1, and an empty section is still a heading
    the reader has to read to discover it says nothing."""
    with repo(tmp_path) as store:
        store.files.upsert("tests/test_bare.py", "sha", "", None)
        store.symbols.insert([
            Symbol(file="tests/test_bare.py", name="test_x", kind="function",
                   line=1, end_line=2, signature=None, decorators=(), doc=None)])
        assert already_imported(store, "[[tests/test_bare.py:1-2]]") == ""
