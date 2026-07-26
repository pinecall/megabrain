"""The whole function an anchor sits INSIDE — its signature and its exits.

MEASURED. Asked to guard `write`, the surface anchored on `try:` and the line
under it. The agent wrote the guard, and then said the plainest thing any of
these reports has said: the spec told it to `raise` inside a `try:` whose
`except` clause it was never shown. Whether that raise survives to the caller
depends entirely on the handler, and the handler was the one part of the edit
site the answer omitted. It reasoned around the gap by hoisting the guard above
the `try:` — an inference the surface forced rather than answered.

Same relation, other repository: an agent inferred a tool's parameter names
from a four-line anchor because the signature above it was not quoted.

The anchor is deliberately SMALL — that is what makes it a usable `find`. The
function around it is what makes the edit correct, and the index knows exactly
where it starts and ends.
"""

from __future__ import annotations

from megabrain.ask._enclosing import enclosing_bodies
from megabrain.chunkers.model import Chunk, Symbol
from megabrain.storage import Store

BODY = "\n".join([
    "def write(path, content):", "    target = resolve(path)", "    try:",
    "        target.parent.mkdir(parents=True, exist_ok=True)",
    "        target.write_text(content)", "    except OSError as e:",
    "        raise ToolError(str(e)) from e", "    return 'ok'"])


def repo(tmp_path) -> Store:
    store = Store(tmp_path)
    store.files.upsert("tools.py", "sha", "", None)
    store.symbols.insert([
        Symbol(file="tools.py", name="write", kind="function", line=1,
               end_line=8, signature=None, decorators=(), doc=None)])
    store.chunks.insert([
        Chunk(file="tools.py", kind="function", name="write", part=None,
              start_line=1, end_line=8, text=BODY, breadcrumb="tools.py")], None)
    return store


def test_the_function_an_anchor_sits_in_is_CITED(tmp_path) -> None:
    """The measured gap. Anchored on the `try:` at L3-4, the reader needs L1-8
    — the signature above it and the `except` below it."""
    with repo(tmp_path) as store:
        out = enclosing_bodies(store, "[[tools.py:3-4]]\nAPPLY insert_before")
    assert "[[tools.py:1-8]]" in out


def test_a_citation_that_ALREADY_spans_the_function_adds_nothing(tmp_path) -> None:
    """The reader has it. A second copy is the duplication the last round's
    reader named as wasted budget."""
    with repo(tmp_path) as store:
        assert enclosing_bodies(store, "[[tools.py:1-8]]\nAPPLY replace_span") == ""


def test_only_ANCHORS_pull_their_function(tmp_path) -> None:
    """A citation with no APPLY is an example to imitate, not a site being
    edited — its surroundings are not the reader's problem."""
    with repo(tmp_path) as store:
        assert enclosing_bodies(store, "look at [[tools.py:3-4]]") == ""


def test_an_anchor_in_no_function_surfaces_nothing(tmp_path) -> None:
    """A module-level anchor has no enclosing symbol, and an empty section is
    a heading the reader must read to learn it says nothing."""
    with repo(tmp_path) as store:
        store.symbols.insert([
            Symbol(file="tools.py", name="LIMIT", kind="constant", line=20,
                   end_line=20, signature=None, decorators=(), doc=None)])
        assert enclosing_bodies(store, "[[tools.py:20-20]]\nAPPLY insert_after") == ""
