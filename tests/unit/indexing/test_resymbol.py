"""Re-extracting the symbols of files that did not change.

The gap was found by measuring a fix that had already shipped. The TS chunker was
taught that a mocha `it('…', fn)` declares a unit; a direct parse of express's
`test/res.attachment.js` went from two symbols to ten, and `megabrain grep` on
the indexed copy kept returning the same three rows — indexing revisits a file
only when its BYTES change, so the improvement was real, invisible, and would
have stayed invisible for every repository already indexed.

`EDGE_SCHEMA` had solved this shape of problem for the graph. Symbols had no
equivalent, and a symbol costs a parse and no embedding, so the fix is free —
which is the point. A fix that requires `--force` is a fix nobody pays for.
"""

from __future__ import annotations

from megabrain.chunkers.model import Symbol
from megabrain.indexing._resymbol import SYMBOL_SCHEMA, resymbol
from megabrain.indexing.builtin import default_registry
from megabrain.storage import Store

SUITE = """\
describe('res.attachment()', function () {
  it('should set the header', function (done) {
    done();
  });
});
"""


def indexed(tmp_path) -> Store:
    """A store as an OLDER engine left it: the file, and the symbols it saw."""
    store = Store(tmp_path)
    store.files.upsert("test/a.js", "sha-unchanged", "", None)
    store.symbols.insert([
        Symbol(file="test/a.js", name="express", kind="const", line=1, end_line=1,
               signature=None, decorators=(), doc=None)])
    return store


def test_an_UNCHANGED_file_gains_what_the_new_extractor_sees(tmp_path) -> None:
    with indexed(tmp_path) as store:
        assert resymbol(store, default_registry(None), {"test/a.js": SUITE},
                        ["test/a.js"]) == 1
        names = {str(e["name"]) for e in store.symbols.read_for("test/a.js")}
    assert any("should set the header" in name for name in names)


def test_the_OLD_symbols_are_REPLACED_not_appended(tmp_path) -> None:
    """Appending would double every symbol on each bump, and a duplicate row is a
    second identical place to jump. The stored `express` binding is not in this
    source, so its absence afterwards is the proof: the rows come from the file
    as it reads NOW, not from the file plus its history."""
    with indexed(tmp_path) as store:
        resymbol(store, default_registry(None), {"test/a.js": SUITE}, ["test/a.js"])
        names = [str(e["name"]) for e in store.symbols.read_for("test/a.js")]
    assert len(names) == len(set(names))
    assert "express" not in names


def test_it_runs_ONCE_and_then_costs_nothing(tmp_path) -> None:
    """A warm index must stay warm: this is a startup cost per bump, not per run."""
    with indexed(tmp_path) as store:
        first = resymbol(store, default_registry(None), {"test/a.js": SUITE},
                         ["test/a.js"])
        second = resymbol(store, default_registry(None), {"test/a.js": SUITE},
                          ["test/a.js"])
    assert (first, second) == (1, 0)


def test_an_index_ALREADY_at_this_schema_is_left_alone(tmp_path) -> None:
    with indexed(tmp_path) as store:
        store.graph.set_meta("symbol_schema", SYMBOL_SCHEMA)
        assert resymbol(store, default_registry(None), {"test/a.js": SUITE},
                        ["test/a.js"]) == 0
        assert [str(e["name"]) for e in store.symbols.read_for("test/a.js")] == \
            ["express"], "nothing was re-read"


def test_the_CHUNKS_and_their_vectors_are_never_touched(tmp_path) -> None:
    """The whole reason this is free. Chunks carry the vectors, and re-embedding
    them is what `--force` is for — so a symbol-only pass must leave them alone."""
    from megabrain.chunkers.model import Chunk

    with indexed(tmp_path) as store:
        store.chunks.insert([Chunk(file="test/a.js", kind="file", name=None, part=None,
                                   start_line=1, end_line=5, text=SUITE,
                                   breadcrumb="a")], None)
        before = len(store.chunks.read_metas())
        resymbol(store, default_registry(None), {"test/a.js": SUITE}, ["test/a.js"])
        assert len(store.chunks.read_metas()) == before


def test_a_file_with_no_strategy_is_skipped_not_emptied(tmp_path) -> None:
    """A source the registry cannot parse must keep whatever it has: replacing
    its symbols with nothing would delete data to no purpose."""
    with indexed(tmp_path) as store:
        store.files.upsert("notes.bin", "sha", "", None)
        assert resymbol(store, default_registry(None), {"notes.bin": "\x00"},
                        ["notes.bin"]) == 0
