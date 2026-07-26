"""The tests that EXERCISE what a change touches — wherever they live.

MEASURED, on the fourth task of the fix loop. Asked to make sinatra's `back`
refuse a cross-host referer, the surface showed the tests beside the anchor,
the change went in clean, and it broke `test_makes_redirecting_back_pretty`
1 800 lines further down the SAME file — a test asserting that `redirect back`
sent you to github.com. That test WAS the bug, pinned. The agent found it only
by running the suite.

Proximity is the wrong relation. `megabrain_search` has always promised "the
tests that pin the behaviour"; this is that promise, computed from the pin
edges the indexer already builds.
"""

from __future__ import annotations

from megabrain.ask._pinned import exercising_tests
from megabrain.chunkers.model import Chunk, Symbol
from megabrain.indexing.pins import write_pin_edges
from megabrain.storage import Store

IMPL = ("class App\n  def back\n    referer_of\n  end\n"
        "  def referer_of\n  end\n  def host_of\n  end\nend")
NEAR = "\n".join(["  it 'x' do", "    back; referer_of; host_of", "  end"] + [f"  # pad {n}" for n in range(60)])
FAR = "\n".join([f"  # pad {n}" for n in range(60)]
                + ["  describe 'back' do", "    it 'redirects back' do",
                   "      back; referer_of; host_of",
                   "      assert_equal 'http://github.com', location", "    end", "  end"])


def repo(tmp_path) -> Store:
    """An impl file its test file PINS, with a near mention and a far one."""
    store = Store(tmp_path)
    for path in ("lib/app.rb", "test/app_test.rb"):
        store.files.upsert(path, "sha", "", None)
    # Three unique symbols: MIN_SHARED is what turns a mention into a pin.
    store.symbols.insert([
        Symbol(file="lib/app.rb", name=f"App.{n}", kind="method", line=line,
               end_line=line + 1, signature=None, decorators=(), doc=None)
        for n, line in (("back", 2), ("referer_of", 6), ("host_of", 8))])
    store.chunks.insert([
        Chunk(file="lib/app.rb", kind="class", name="App", part=None, start_line=1,
              end_line=5, text=IMPL, breadcrumb="lib/app.rb"),
        Chunk(file="test/app_test.rb", kind="block", name=None, part=None,
              start_line=1, end_line=63, text=NEAR, breadcrumb="t"),
        Chunk(file="test/app_test.rb", kind="block", name=None, part=None,
              start_line=64, end_line=128, text=FAR, breadcrumb="t"),
    ], None)
    write_pin_edges(store)
    return store


def test_a_DISTANT_test_of_the_changed_symbol_is_surfaced(tmp_path) -> None:
    """The measured failure. The near block is already cited; the one that
    breaks is 60 lines past it and nobody looked."""
    with repo(tmp_path) as store:
        out = exercising_tests(store, "[[lib/app.rb:2-4]]\n[[test/app_test.rb:1-63]]")
    assert "Tests that pin this behaviour" in out
    assert "test/app_test.rb" in out


def test_what_is_ALREADY_cited_is_not_cited_again(tmp_path) -> None:
    """Skipped by SPAN, never by file — the block that broke sat in the same
    file as the ones already shown."""
    with repo(tmp_path) as store:
        out = exercising_tests(store, "[[lib/app.rb:2-4]]\n[[test/app_test.rb:1-128]]")
    assert out == "", "re-cited a span the reader already has"


def test_a_test_that_does_NOT_pin_the_file_is_ignored(tmp_path) -> None:
    """`back` is an English word. Matched repo-wide it returned two unrelated
    specs and a helper module, pushing the block that breaks off the list — a
    pin is a fact the indexer computed, a mention is a coincidence."""
    with repo(tmp_path) as store:
        store.files.upsert("test/other_test.rb", "sha", "", None)
        store.chunks.insert([Chunk(file="test/other_test.rb", kind="block", name=None,
                                   part=None, start_line=1, end_line=2,
                                   text="# roll back the transaction", breadcrumb="o")],
                            None)
        out = exercising_tests(store, "[[lib/app.rb:2-4]]\n[[test/app_test.rb:1-63]]")
    assert "other_test" not in out


def test_a_FIXTURE_that_asserts_nothing_is_ignored(tmp_path) -> None:
    """MEASURED as the one section a reader skimmed and discarded. A Sinatra
    app under `test/integration/` surfaced because a route in it is named for
    the symbol — the path says test, the content says fixture. A mention is not
    a pin; a claim is."""
    with repo(tmp_path) as store:
        store.files.upsert("test/integration/app.rb", "sha", "", None)
        store.chunks.insert([Chunk(
            file="test/integration/app.rb", kind="block", name=None, part=None,
            start_line=1, end_line=3,
            text="get '/back' do\n  back; referer_of; host_of\nend",
            breadcrumb="i")], None)
        write_pin_edges(store)
        out = exercising_tests(store, "[[lib/app.rb:2-4]]\n[[test/app_test.rb:1-63]]")
    assert "integration/app.rb" not in out


def test_a_change_touching_NO_symbol_surfaces_nothing(tmp_path) -> None:
    """A citation that declares nothing has nothing to be pinned by, and a
    section with no content is noise the reader still has to read."""
    with repo(tmp_path) as store:
        assert exercising_tests(store, "[[lib/app.rb:1-1]]") == ""
