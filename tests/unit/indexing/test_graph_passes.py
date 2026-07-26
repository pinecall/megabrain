"""The two graph passes together — and the one ordering bug between them.

MEASURED on click, and it deleted a whole relation without an error. Bumping
EDGE_SCHEMA rewrites every file's edges while no file's CONTENT changed.
`write_edges` swaps a file's rows with `replace_edges`, which drops all of that
file's outgoing edges — and a test file's outgoing edges include its pins. The
pin pass then declined to run, because it only ran when content moved or the
pin schema changed, so the pins stayed deleted: 352 edges became 262, every one
of the 90 lost ones a pin.

That silently disables `exercising_tests`, the reason the pin relation exists —
the surface that quotes the test 1 600 lines away which pins the behaviour a
change is about to break.
"""

from __future__ import annotations

from megabrain.chunkers.model import Chunk, Symbol
from megabrain.indexing.builtin import default_registry
from megabrain.indexing.edges._rebuild import graph_passes
from megabrain.indexing.strategies import EDGE_SCHEMA
from megabrain.storage import PIN_KIND, Store

# Three shared symbols: MIN_SHARED is what turns mentions into a pin.
IMPL = "def redirect_back():\n    referer_of()\n    fallback_uri()\n"
TEST = "def test_it():\n    redirect_back(); referer_of(); fallback_uri()\n"
SOURCES = {"app.py": IMPL, "test_app.py": TEST}


def seeded(tmp_path) -> Store:
    """An index whose graph is already built and current."""
    store = Store(tmp_path)
    for relpath, text in SOURCES.items():
        store.files.upsert(relpath, "sha", "", None)
        store.chunks.insert([Chunk(file=relpath, kind="file", name=None, part=None,
                                   start_line=1, end_line=1 + text.count("\n"),
                                   text=text, breadcrumb=relpath)], None)
    store.symbols.insert([
        Symbol(file="app.py", name=n, kind="function", line=i, end_line=i + 1,
               signature=None, decorators=(), doc=None)
        for i, n in enumerate(("redirect_back", "referer_of", "fallback_uri"), start=1)])
    graph_passes(store, default_registry(), SOURCES, [])
    store.graph.set_meta("edge_schema", EDGE_SCHEMA)
    return store


def test_the_seeded_index_really_has_a_pin(tmp_path) -> None:
    """Guard on the fixture: if this stops holding, the regression test below
    would pass for the wrong reason."""
    with seeded(tmp_path) as store:
        assert store.graph.sources_of("app.py", PIN_KIND) == {"test_app.py"}


def test_an_EDGE_SCHEMA_bump_does_not_erase_the_pins(tmp_path) -> None:
    """The measured bug. Every file is rewritten, no content changed — and the
    pins a test file owns must survive that rewrite."""
    with seeded(tmp_path) as store:
        store.graph.set_meta("edge_schema", EDGE_SCHEMA - 1)   # the bump
        graph_passes(store, default_registry(), SOURCES, [])
        assert store.graph.sources_of("app.py", PIN_KIND) == {"test_app.py"}, \
            "the extractor's rewrite deleted the pins and nothing put them back"


def test_a_pass_with_nothing_to_do_leaves_the_pins_alone(tmp_path) -> None:
    """The other half: an up-to-date index must not pay for a pin recompute on
    every call, and must not lose them either."""
    with seeded(tmp_path) as store:
        assert graph_passes(store, default_registry(), SOURCES, []) == 0
        assert store.graph.sources_of("app.py", PIN_KIND) == {"test_app.py"}
