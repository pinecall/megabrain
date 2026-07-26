"""The definitions of the helpers the surface names — cited by the ENGINE.

MEASURED, across the four tasks of the fix loop. In three of four, the agent's
very next call after `megabrain_code` was `megabrain_ask`, and all three asks
were the same request: show me the BODY of a helper the surface told me to
call — `content_type` and `attachment` on one task, `resolve_path` on another.
"CITE EVERY HELPER YOU TELL THEM TO REUSE" was a prompt clause, and a clause
is a request the model can ignore — and did, three times out of four.

This is that clause as a mechanism: every backticked name in the surface that
resolves to ONE definition in the index gets its definition cited, by the
engine, with nothing to forget.
"""

from __future__ import annotations

from megabrain.ask.checks.callees import named_definitions
from megabrain.chunkers.model import Symbol
from megabrain.storage import Store


def repo(tmp_path) -> Store:
    """One unambiguous helper, one name defined twice, one container class."""
    store = Store(tmp_path)
    for path in ("lib/base.rb", "lib/render.rb", "app/render.rb"):
        store.files.upsert(path, "sha", "", None)
    store.symbols.insert([
        Symbol(file="lib/base.rb", name="Base", kind="class", line=1,
               end_line=200, signature=None, decorators=(), doc=None),
        Symbol(file="lib/base.rb", name="Base.content_type", kind="method",
               line=10, end_line=14, signature=None, decorators=(), doc=None),
        Symbol(file="lib/render.rb", name="A.render", kind="method", line=3,
               end_line=6, signature=None, decorators=(), doc=None),
        Symbol(file="app/render.rb", name="B.render", kind="method", line=9,
               end_line=12, signature=None, decorators=(), doc=None),
    ])
    return store


def test_a_BACKTICKED_helper_is_cited_at_its_definition(tmp_path) -> None:
    """The measured gap: the spec says "call `content_type`" and the agent's
    next tool call is an ask for its body. Now the body arrives with the spec."""
    with repo(tmp_path) as store:
        out = named_definitions(
            store, "Call `content_type` to set it.\n[[lib/base.rb:50-60]]")
    assert "[[lib/base.rb:10-14]]" in out


def test_a_definition_ALREADY_in_front_of_the_reader_is_not_repeated(tmp_path) -> None:
    """Skipped by SPAN overlap: if the anchor citation already shows the
    helper, citing it again is the same range twice."""
    with repo(tmp_path) as store:
        out = named_definitions(store, "Call `content_type`.\n[[lib/base.rb:8-20]]")
    assert out == ""


def test_an_AMBIGUOUS_name_is_skipped(tmp_path) -> None:
    """Two files define `render`. A citation that could land on either looks
    authoritative and might be the wrong one — same rule as the navigator."""
    with repo(tmp_path) as store:
        out = named_definitions(store, "Use `render` for the body.")
    assert out == ""


def test_a_file_the_surface_CITES_disambiguates(tmp_path) -> None:
    """Ambiguous repo-wide, unique among the files the surface already talks
    about — the change's own file is the jump the reader means."""
    with repo(tmp_path) as store:
        out = named_definitions(store, "Use `render`.\n[[app/render.rb:30-40]]")
    assert "[[app/render.rb:9-12]]" in out
    assert "lib/render.rb" not in out


def test_a_CLASS_is_never_pasted_for_its_name(tmp_path) -> None:
    """`Base` names a 200-line container. Its definition is the whole file —
    citing it answers nothing and costs everything."""
    with repo(tmp_path) as store:
        assert named_definitions(store, "Subclass `Base` here.") == ""


def test_a_name_the_index_does_not_KNOW_surfaces_nothing(tmp_path) -> None:
    """Prose backticks parameters and literals too — `arg`, `nil`. A name with
    no definition produces no section, not an empty header."""
    with repo(tmp_path) as store:
        assert named_definitions(store, "Return `nil` when `frobnicate` is empty.") == ""


def test_a_RUBY_bang_method_resolves(tmp_path) -> None:
    """MEASURED on sinatra. Asked when before filters run, the answer said
    `dispatch!` was "not shown in the provided chunks" — and this pass could not
    rescue it, because the name was cut at the bang and `dispatch` matches
    nothing. Sinatra's whole request lifecycle is bang methods, so the omission
    hit exactly the symbols the walkthrough needed."""
    with repo(tmp_path) as store:
        store.files.upsert("lib/base.rb", "sha", "", None)
        store.symbols.insert([
            Symbol(file="lib/base.rb", name="Base.dispatch!", kind="method",
                   line=1195, end_line=1205, signature=None, decorators=(), doc=None),
            Symbol(file="lib/base.rb", name="Base.empty?", kind="method",
                   line=40, end_line=42, signature=None, decorators=(), doc=None)])
        out = named_definitions(store, "the flow runs through `dispatch!` when `empty?`")
    assert "[[lib/base.rb:1195-1205]]" in out
    assert "[[lib/base.rb:40-42]]" in out


def test_a_DOC_heading_is_never_the_definition(tmp_path) -> None:
    """MEASURED noise. A markdown heading is a symbol too, so `ToolError`
    matched `tools.md` and pasted 24 lines of user-facing prose under a heading
    promising a definition. The agent named it as the one thing it did not
    read. A definition lives in CODE."""
    with repo(tmp_path) as store:
        store.files.upsert("docs/tools.md", "sha", "", None)
        store.symbols.insert([
            Symbol(file="docs/tools.md", name="ToolError", kind="h2",
                   line=79, end_line=102, signature=None, decorators=(), doc=None)])
        assert named_definitions(store, "Raise `ToolError` on failure.") == ""
