"""Citations become verbatim source — and a citation has a ceiling.

The engine produces the code so the model cannot retype it wrong. What the
model CAN do is ask for too much: told to cite "one test, or one method — not
the class or describe that contains it", it cited a 117-line container holding
fifteen tests, 55% of the whole answer, to demonstrate what one of them looks
like. Asking a third time was not going to work, so the ceiling is enforced.

Display only. The APPLY markers that build an edit are read from the RAW text
before any quoting, so a cut here can never shorten an anchor.
"""

from __future__ import annotations

from megabrain.ask.citing._quote import quote_citations
from megabrain.chunkers.model import Chunk
from megabrain.storage import Store

SOURCE = "\n".join(f"line {n}" for n in range(1, 121))


def indexed(tmp_path) -> Store:
    store = Store(tmp_path)
    store.files.upsert("app.rb", "sha", "", None)
    store.chunks.insert([Chunk(file="app.rb", kind="file", name=None, part=None,
                               start_line=1, end_line=120, text=SOURCE,
                               breadcrumb="app.rb")], None)
    return store


def test_a_citation_becomes_the_real_lines(tmp_path) -> None:
    with indexed(tmp_path) as store:
        out = quote_citations("see [[app.rb:3-5]]", store)
    assert "line 3\nline 4\nline 5" in out and "```ruby" in out


def test_an_OVERSIZED_citation_is_elided_and_says_so(tmp_path) -> None:
    """Cut from the MIDDLE, not the tail. MEASURED: cutting the tail dropped
    the `end` that closed the block an `insert_after` was aimed at, so the
    instruction referred to a line the answer never showed."""
    with indexed(tmp_path) as store:
        out = quote_citations("[[app.rb:1-117]]", store)
    assert "line 1\n" in out, "lost the opening of the block"
    assert "line 117" in out, "lost the closing of the block"
    assert "elided" in out and "L1-117" in out, "the real range is not named"


def test_a_citation_within_the_ceiling_is_untouched(tmp_path) -> None:
    with indexed(tmp_path) as store:
        out = quote_citations("[[app.rb:1-10]]", store)
    assert "elided" not in out and "line 10" in out


def test_a_bracket_NO_grammar_accepted_is_dropped(tmp_path) -> None:
    """MEASURED: served a body with real line numbers, the model cited it as
    `[[1214-1215]]` — neither a chunk index nor a path — and both splicers passed
    over it, so the reader got literal brackets mid-sentence. Dropped, the stance
    `splice` already takes on a citation of a chunk never offered."""
    with indexed(tmp_path) as store:
        out = quote_citations("after filters run [[1214-1215]] unless static.", store)
    assert "[[" not in out
    assert "after filters run unless static." in out, "the space was left behind"


def test_the_SAME_range_twice_is_a_back_reference(tmp_path) -> None:
    """MEASURED: the same body arrived as the anchor and again under "Pattern
    to follow" — ~60 duplicated lines the reader named as the budget the
    elided closing lines should have come from."""
    with indexed(tmp_path) as store:
        out = quote_citations("[[app.rb:3-5]] and again [[app.rb:3-5]]", store)
    assert out.count("line 4") == 1, "quoted the same range twice"
    assert "quoted above" in out


def test_a_range_beyond_the_file_is_CLAMPED_not_dropped(tmp_path) -> None:
    """An off-by-a-bit range is the common model error; refusing it outright
    would lose a quotation that is nearly right."""
    with indexed(tmp_path) as store:
        out = quote_citations("[[app.rb:118-400]]", store)
    assert "line 120" in out


def test_a_file_that_is_not_indexed_says_so_instead_of_inventing(tmp_path) -> None:
    with indexed(tmp_path) as store:
        out = quote_citations("[[nope.rb:1-3]]", store)
    assert "no file" in out and "```" not in out


def test_a_citation_INCLUDES_the_decorators_above_it(tmp_path) -> None:
    """MEASURED: a "complete sibling" cited from `async def test_…` left
    `@needs_pydantic_v2` on the line above, and the agent opened the file to
    find out what decorated every test in it. A decorated declaration BEGINS at
    its first decorator — citing from the `def` shows a function the file does
    not contain."""
    source = ("import pytest\n\n@pytest.mark.skipif(True)\n@needs_v2\n"
              "def test_thing():\n    assert 1\n")
    store = Store(tmp_path)
    store.files.upsert("t.py", "sha", "", None)
    store.chunks.insert([Chunk(file="t.py", kind="file", name=None, part=None,
                               start_line=1, end_line=6, text=source,
                               breadcrumb="t.py")], None)
    with store:
        out = quote_citations("[[t.py:5-6]]", store)
    assert "@needs_v2" in out and "@pytest.mark.skipif" in out
    assert "import pytest" not in out, "widened past the decorators"
