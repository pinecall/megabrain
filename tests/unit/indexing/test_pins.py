"""Which test PINS which implementation file.

The gap this closes is not a tuning problem, it is a missing engine. `sinatra`
indexes 162 files and produced **zero** edges: Ruby, Go, Rust, PHP, C, C++,
Java and C# all reach `GrammarStrategy`, whose `edges()` returns None. On those
repositories the graph does not exist and retrieval runs on cosine alone.

Measured consequence, on a real task ("add a redirect_back helper…"): the two
files the change had to edit were `lib/sinatra/base.rb` and
`test/helpers_test.rb`. The test file was **absent from the bundle entirely**,
so an agent using the tool spent exactly the turns it would have spent with
grep. `megabrain_search` promises "the tests that pin the behaviour"; nothing
was delivering it.

Imports would not have fixed it: `helpers_test.rb` requires only
`test_helper`, so the chain reaches `base.rb` in three hops no one-hop
neighbour lookup follows. What DOES connect them is that the test names 47
symbols `base.rb` alone declares.
"""

from __future__ import annotations

from megabrain.chunkers.model import Chunk, Symbol
from megabrain.indexing.edges.pins import MIN_SHARED, write_pin_edges
from megabrain.storage import PIN_KIND, Store


def chunk(relpath: str, text: str) -> Chunk:
    return Chunk(file=relpath, kind="file", name=None, part=None, start_line=1,
                 end_line=1 + text.count("\n"), text=text, breadcrumb=relpath)


def declare(relpath: str, *names: str) -> list[Symbol]:
    return [Symbol(file=relpath, name=n, kind="method", line=1, end_line=2,
                   signature=None, decorators=(), doc=None) for n in names]


def repo(tmp_path, files: dict[str, tuple[list[Symbol], str]]) -> Store:
    """An index with just symbols and chunk text — all a pin needs."""
    store = Store(tmp_path)
    for relpath, (symbols, text) in files.items():
        store.files.upsert(relpath, "sha", "", None)
        store.symbols.insert(symbols)
        store.chunks.insert([chunk(relpath, text)], None)
    return store


def test_a_test_naming_a_files_symbols_PINS_it(tmp_path) -> None:
    """The measured case, in miniature: no import connects them, the shared
    vocabulary does."""
    with repo(tmp_path, {
        "lib/app.rb": (declare("lib/app.rb", "redirect_back", "referer_of",
                               "fallback_uri"), "class App; end"),
        "test/app_test.rb": ([], "redirect_back referer_of fallback_uri"),
    }) as store:
        assert write_pin_edges(store) == 1
        assert store.graph.sources_of("lib/app.rb", PIN_KIND) == {"test/app_test.rb"}


def test_an_AMBIGUOUS_symbol_mints_no_edge(tmp_path) -> None:
    """The phantom-edge rule `edges.py` rests on, borrowed from
    `SymbolTable.name_counts`: a name two files declare cannot be evidence
    about either. An edge that could point anywhere hands a reader an
    unrelated file AS evidence, which is worse than no edge at all."""
    with repo(tmp_path, {
        "lib/one.rb": (declare("lib/one.rb", "process", "handle", "dispatch"), "one"),
        "lib/two.rb": (declare("lib/two.rb", "process", "handle", "dispatch"), "two"),
        "test/x_test.rb": ([], "process handle dispatch"),
    }) as store:
        assert write_pin_edges(store) == 0


def test_a_PASSING_MENTION_is_not_a_pin(tmp_path) -> None:
    """One shared name is a mention; MIN_SHARED is what makes it a claim."""
    names = [f"unique_symbol_{i}" for i in range(MIN_SHARED + 1)]
    with repo(tmp_path, {
        "lib/app.rb": (declare("lib/app.rb", *names), "class App; end"),
        "test/thin_test.rb": ([], names[0]),
        "test/real_test.rb": ([], " ".join(names[:MIN_SHARED])),
    }) as store:
        write_pin_edges(store)
        pinning = store.graph.sources_of("lib/app.rb", PIN_KIND)
        assert pinning == {"test/real_test.rb"}


def test_a_TEST_is_never_the_pinned_end(tmp_path) -> None:
    """A test helper sharing a name with production code would otherwise make
    every other test look like it pins that test."""
    with repo(tmp_path, {
        "test/helper.rb": (declare("test/helper.rb", "make_app", "with_server",
                                   "reset_state"), "helper"),
        "test/x_test.rb": ([], "make_app with_server reset_state"),
    }) as store:
        assert write_pin_edges(store) == 0


def test_the_pass_does_not_ERASE_other_edge_kinds(tmp_path) -> None:
    """`replace_edges` drops everything a file points at, which is right for an
    extractor owning a file's whole graph and wrong for a pass owning one
    relation. Using it here would silently delete the import edges a language
    extractor had just written."""
    with repo(tmp_path, {
        "lib/app.rb": (declare("lib/app.rb", "alpha_one", "beta_two",
                               "gamma_three"), "app"),
        "test/app_test.rb": ([], "alpha_one beta_two gamma_three"),
    }) as store:
        store.graph.replace_edges("test/app_test.rb", [("lib/helper.rb", "import")])
        write_pin_edges(store)
        kinds = {kind for src, _, kind in store.graph.all_edges()
                 if src == "test/app_test.rb"}
        assert kinds == {"import", PIN_KIND}


def test_a_pin_that_STOPPED_being_true_is_removed(tmp_path) -> None:
    """Both ends can change, so the relation is recomputed rather than
    invalidated per file — an edge whose two files both still exist can still
    have stopped being true."""
    with repo(tmp_path, {
        "lib/app.rb": (declare("lib/app.rb", "alpha_one", "beta_two",
                               "gamma_three"), "app"),
        "test/app_test.rb": ([], "alpha_one beta_two gamma_three"),
    }) as store:
        write_pin_edges(store)
        assert store.graph.sources_of("lib/app.rb", PIN_KIND)
        store.db.execute("UPDATE chunks SET text='nothing in common' "
                         "WHERE file='test/app_test.rb'")
        write_pin_edges(store)
        assert store.graph.sources_of("lib/app.rb", PIN_KIND) == set()
