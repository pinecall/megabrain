"""The edit surface, turned into operations `megabrain_replace` can apply.

The engine supplies the half it can be exactly right about — which file, which
lines, the anchor text VERBATIM from the index — and leaves a HOLE where the
caller's own code goes.

That division is measured. Asked to guard the `write` tool against non-regular
files, the engine found both files and both insertion points in a 1 220-file
repository, and then authored a guard that ran AFTER the write it was guarding,
inside an unclosed `try:` that does not compile. The agent spent four retrieval
calls and two reads undoing it and finished slower than the arm with no
megabrain at all — while on an easier change the same mechanism had cut 11
turns to 5. Nobody can tell in advance which of the two a task is, which is
what made authoring code unusable as a default.
"""

from __future__ import annotations

from megabrain.ask._operations import operations_from
from megabrain.chunkers.model import Chunk
from megabrain.contracts.edits import NEW_CODE
from megabrain.storage import Store

SOURCE = """class App
  def one
    1
  end
end"""


def indexed(tmp_path, source: str = SOURCE) -> Store:
    store = Store(tmp_path)
    store.files.upsert("app.rb", "sha", "", None)
    store.chunks.insert([Chunk(file="app.rb", kind="class", name="App", part=None,
                               start_line=1, end_line=len(source.split("\n")),
                               text=source, breadcrumb="app.rb")], None)
    return store


def surface(span: str = "2-4", mode: str = "insert_after") -> str:
    return (f"## app.rb — add two\n[[app.rb:{span}]]\nAPPLY {mode}\n"
            "It must call `one` rather than recomputing what it returns.")


def test_the_FIND_comes_from_the_index_not_the_model(tmp_path) -> None:
    """Exact by construction: no model ever types the anchor, so an edit can
    never fail on a mistyped one."""
    with indexed(tmp_path) as store:
        ops = operations_from(surface(), store)
    assert len(ops) == 1
    assert ops[0]["find"] == "  def one\n    1\n  end"
    assert ops[0]["file"] == "app.rb"


def test_insert_after_KEEPS_the_anchor_and_leaves_a_HOLE(tmp_path) -> None:
    """The anchor is repeated into `replace` so the caller does not retype it
    either — they fill the marker and nothing else."""
    with indexed(tmp_path) as store:
        ops = operations_from(surface(), store)
    assert ops[0]["replace"] == f"{ops[0]['find']}\n{NEW_CODE}"


def test_replace_span_is_ONLY_the_hole(tmp_path) -> None:
    """Replacing means the cited lines go away, so nothing of them survives
    into the new text."""
    with indexed(tmp_path) as store:
        ops = operations_from(surface(mode="replace_span"), store)
    assert ops[0]["replace"] == NEW_CODE


def test_no_code_the_MODEL_wrote_reaches_the_batch(tmp_path) -> None:
    """The regression that matters. Even when the surface contains a fenced
    block — a model reverting to its old habit — none of it becomes an edit."""
    tempted = surface() + "\n```ruby\ndef two\n  2\nend\n```\n"
    with indexed(tmp_path) as store:
        ops = operations_from(tempted, store)
    assert "def two" not in ops[0]["replace"]
    assert ops[0]["replace"].endswith(NEW_CODE)


def test_a_range_that_does_not_EXIST_yields_no_operation(tmp_path) -> None:
    """A wrong operation is worse than none — it edits. The prose still reaches
    the reader, which is where they already were."""
    with indexed(tmp_path) as store:
        assert operations_from(surface(span="90-99"), store) == []


def test_an_unmarked_surface_yields_NOTHING(tmp_path) -> None:
    """Only an explicit APPLY marker becomes an operation: a citation on its
    own is a quotation, and quoting code must never write it."""
    with indexed(tmp_path) as store:
        assert operations_from("## app.rb\n[[app.rb:2-4]]\njust prose", store) == []


def test_every_marked_edit_in_the_surface_is_collected(tmp_path) -> None:
    """One call applies the WHOLE change — that is the point of the batch."""
    two = surface() + "\n\n" + surface(span="1-2")
    with indexed(tmp_path) as store:
        assert len(operations_from(two, store)) == 2


def test_insert_before_puts_the_hole_ABOVE_the_anchor(tmp_path) -> None:
    """MEASURED: its absence produced a wrong edit. Guarding an operation means
    adding code BEFORE the thing it guards, and with only `insert_after` the
    model cited the whole function body and said "after" — putting the guard
    after the write it was supposed to prevent. Its own prose said "before";
    the mode it needed did not exist."""
    with indexed(tmp_path) as store:
        ops = operations_from(surface(mode="insert_before"), store)
    assert ops[0]["replace"] == f"{NEW_CODE}\n{ops[0]['find']}"
