"""The edit surface, turned into operations `megabrain_replace` can apply.

MEASURED: handed the surface as prose, an agent spent two `replace` calls and
a `Read` applying a two-file change it had already been given — it rebuilt the
exact-string operations by hand, one file at a time.

The `find` is built HERE, from the index, never by the model. That is what
makes it safe: `replace` matches exact text, so a model retyping the anchor
with one space wrong turns a valid edit into a refusal. The model names a span
it already cited and the lines to add; the engine reads that span out of the
index. Exact by construction.
"""

from __future__ import annotations

from megabrain.ask._operations import operations_from
from megabrain.chunkers.model import Chunk
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


def surface(body: str, span: str = "2-4", mode: str = "insert_after") -> str:
    return f"## app.rb — add two\n[[app.rb:{span}]]\nAPPLY {mode}\n```ruby\n{body}\n```"


def test_the_FIND_comes_from_the_index_not_the_model(tmp_path) -> None:
    """Exact by construction: the model never types the anchor back."""
    with indexed(tmp_path) as store:
        ops = operations_from(surface("  def two\n    2\n  end"), store)
    assert len(ops) == 1
    assert ops[0]["find"] == "  def one\n    1\n  end"
    assert ops[0]["file"] == "app.rb"


def test_insert_after_KEEPS_the_anchor_and_appends(tmp_path) -> None:
    with indexed(tmp_path) as store:
        ops = operations_from(surface("  def two\n    2\n  end"), store)
    assert ops[0]["replace"].startswith(ops[0]["find"])
    assert ops[0]["replace"].endswith("  def two\n    2\n  end")


def test_replace_span_DROPS_the_anchor(tmp_path) -> None:
    with indexed(tmp_path) as store:
        ops = operations_from(surface("  def uno\n    1\n  end", mode="replace_span"),
                              store)
    assert ops[0]["replace"] == "  def uno\n    1\n  end"


def test_the_new_block_is_REINDENTED_to_its_sibling(tmp_path) -> None:
    """Told twice — in rules and by example — to match the anchor's
    indentation, the model produced a method two spaces deeper than the one it
    sat beside. Ruby did not care and a linter would have, so the engine
    straightens it instead of asking again."""
    with indexed(tmp_path) as store:
        ops = operations_from(surface("      def two\n        2\n      end"), store)
    added = ops[0]["replace"][len(ops[0]["find"]):]
    assert added == "\n  def two\n    2\n  end", "not shifted to the sibling's level"


def test_reindenting_moves_the_block_WITHOUT_reformatting_it(tmp_path) -> None:
    """One delta for the whole block: relative structure is the author's, the
    starting column is the file's."""
    with indexed(tmp_path) as store:
        ops = operations_from(surface("def two\n  if x\n    2\n  end\nend"), store)
    added = ops[0]["replace"][len(ops[0]["find"]):]
    assert added == "\n  def two\n    if x\n      2\n    end\n  end"


def test_a_range_that_does_not_EXIST_yields_no_operation(tmp_path) -> None:
    """A wrong operation is worse than none — it edits. Prose still reaches
    the reader, which is where they already were."""
    with indexed(tmp_path) as store:
        assert operations_from(surface("  x", span="90-99"), store) == []


def test_an_unmarked_surface_yields_NOTHING(tmp_path) -> None:
    """Only an explicit APPLY marker becomes an edit: a citation on its own is
    a quotation, and quoting code must never write it."""
    with indexed(tmp_path) as store:
        assert operations_from("## app.rb\n[[app.rb:2-4]]\njust prose", store) == []


def test_every_marked_edit_in_the_surface_is_collected(tmp_path) -> None:
    """One call applies the WHOLE change — that is the point of the batch."""
    two = surface("  def two\n    2\n  end") + "\n\n" + surface("  def three\n    3\n  end")
    with indexed(tmp_path) as store:
        assert len(operations_from(two, store)) == 2
