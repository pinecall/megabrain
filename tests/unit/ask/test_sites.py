"""The edit sites, resolved: the model names symbols, the ENGINE numbers them.

`grep` exists because the host's editor makes you open the file anyway. Citing
the code back is work paid for twice — that is why `megabrain_code` was retired.
What a grep replacement owes you is narrower: which files, which symbols in
them, one line on why each matters, and the exact line range to jump to.

The split of labour is the whole design. Asking the model for line numbers was
already measured and rejected in `prompt.py`: "unnumbered, `[[k:lo-hi]]`
citations landed a few lines off and cut functions mid-body." So the model names
`Session.create` and the engine reads L474-489 out of the symbol table, where it
cannot be off by one.
"""

from __future__ import annotations

from megabrain.ask.sites.sites import sites_from
from megabrain.chunkers.model import Symbol
from megabrain.storage import Store


def repo(tmp_path) -> Store:
    store = Store(tmp_path)
    for path in ("lib/app.rb", "test/app_test.rb"):
        store.files.upsert(path, "sha", "", None)
    store.symbols.insert([
        Symbol(file="lib/app.rb", name="App.send_file", kind="method", line=425,
               end_line=448, signature=None, decorators=(), doc=None),
        Symbol(file="lib/app.rb", name="App.attachment", kind="method", line=415,
               end_line=423, signature=None, decorators=(), doc=None),
        Symbol(file="test/app_test.rb", name="test_sends", kind="method", line=57,
               end_line=62, signature=None, decorators=(), doc=None),
    ])
    return store


def test_a_named_symbol_gets_its_REAL_line_range(tmp_path) -> None:
    """The core trade: the model supplies the name, the index supplies L425-448
    — a range it cannot miscount."""
    with repo(tmp_path) as store:
        out = sites_from(store, "lib/app.rb | send_file | sends a file as the body")
    assert "L425-448" in out
    assert "sends a file as the body" in out


def test_several_symbols_in_one_file_are_grouped(tmp_path) -> None:
    """One heading per file, because the reader opens a FILE and then jumps."""
    with repo(tmp_path) as store:
        out = sites_from(store, "lib/app.rb | send_file | the pattern\n"
                                "lib/app.rb | attachment | sets the header")
    assert out.count("lib/app.rb") == 1, "the file was announced twice"
    assert "L425-448" in out and "L415-423" in out


def test_a_symbol_the_index_does_not_KNOW_is_dropped(tmp_path) -> None:
    """A line the engine cannot number is a line the reader cannot jump to, and
    a plausible-looking range invented for it is worse than its absence."""
    with repo(tmp_path) as store:
        out = sites_from(store, "lib/app.rb | invented_helper | not real")
    assert "invented_helper" not in out


def test_a_file_the_index_does_not_know_is_dropped(tmp_path) -> None:
    with repo(tmp_path) as store:
        assert sites_from(store, "nope.rb | thing | not real") == ""


def test_a_long_description_is_CUT(tmp_path) -> None:
    """The point of this render is that it is small. An unbounded note turns it
    back into the walkthrough it exists to replace."""
    with repo(tmp_path) as store:
        out = sites_from(store, f"lib/app.rb | send_file | {'x' * 300}")
    assert len(max(out.split("\n"), key=len)) < 160


def test_prose_around_the_rows_is_ignored(tmp_path) -> None:
    """Models preface and summarise. Only the pipe-shaped rows are data."""
    with repo(tmp_path) as store:
        out = sites_from(store, "Here is what I found:\n\n"
                                "lib/app.rb | send_file | the body setter\n\n"
                                "That should be everything you need.")
    assert "L425-448" in out
    assert "That should be everything" not in out


def test_a_RUBY_or_CPP_spelled_symbol_resolves(tmp_path) -> None:
    """MEASURED: the model answered `Sinatra::Helpers#send_file` for a symbol the
    index stores as `Sinatra.Helpers.send_file`, and splitting on `.` alone left
    `Helpers#send_file`, matching nothing. It is reading SOURCE, so it spells
    names the way that language does."""
    with repo(tmp_path) as store:
        for spelling in ("Sinatra::Helpers#send_file", "App#send_file",
                         "Helpers::send_file", "send_file"):
            out = sites_from(store, f"lib/app.rb | {spelling} | the pattern")
            assert "L425-448" in out, f"did not resolve {spelling}"


def test_a_symbol_spanning_a_WHOLE_CLASS_is_not_a_site(tmp_path) -> None:
    """MEASURED on sinatra: asked where to add tests, the model named
    `HelpersTest` and the index numbered it L5-2109. A 2 100-line class as a
    place to jump to is no better than the filename."""
    with repo(tmp_path) as store:
        store.symbols.insert([
            Symbol(file="test/app_test.rb", name="HelpersTest", kind="class",
                   line=5, end_line=2109, signature=None, decorators=(), doc=None)])
        out = sites_from(store, "test/app_test.rb | HelpersTest | where tests go")
    assert "HelpersTest" not in out


def test_a_QUALIFIED_name_beats_the_base_class_of_the_same_method(tmp_path) -> None:
    """MEASURED on click: asked for `Choice.get_metavar`, matching the last
    segment alone returned `ParamType.get_metavar` — the base class, 257 lines
    earlier, because it comes first in the file. A reader sent there reads the
    wrong override and finds nothing to change."""
    with repo(tmp_path) as store:
        store.files.upsert("types.py", "sha", "", None)
        store.symbols.insert([
            Symbol(file="types.py", name="ParamType.get_metavar", kind="method",
                   line=158, end_line=159, signature=None, decorators=(), doc=None),
            Symbol(file="types.py", name="Choice.get_metavar", kind="method",
                   line=415, end_line=430, signature=None, decorators=(), doc=None)])
        out = sites_from(store, "types.py | Choice.get_metavar | update the help")
    assert "L415-430" in out
    assert "L158-159" not in out, "matched the base class instead of the override"


def test_a_BARE_name_still_resolves_when_only_one_class_has_it(tmp_path) -> None:
    """The fallback has to stay: the model writes `send_file` far more often than
    it writes the qualified form."""
    with repo(tmp_path) as store:
        assert "L425-448" in sites_from(store, "lib/app.rb | send_file | pattern")
