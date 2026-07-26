"""Every symbol that literally mentions the task's own identifiers.

MEASURED, head to head, and this is the lane that lost it. Asked to add
`show_envvar_value` beside the existing `show_envvar`, a plain `grep show_envvar`
returned all six sites in one call — the reader's words: "the initial grep gave
all 6 core.py sites at once". `megabrain_grep` named two, and the ones it left
out were the one where the logic goes (`get_help_extra`, found only because it
happens to start two lines after a range that WAS given) and a TypedDict in
another file that had to gain a key.

A tool that replaces grep has to return at least what grep returns. The model is
good at the site whose text mentions nothing — that is the half grep cannot do —
and hopeless as a guarantee of completeness. So completeness stops being asked
for and becomes computed: the identifiers in the TASK, matched literally against
the index, resolved to the symbols that contain them.
"""

from __future__ import annotations

from megabrain.ask.sites.mentions import mentioned_sites
from megabrain.chunkers.model import Chunk, Symbol
from megabrain.storage import Store

BODY = "\n".join([
    "class Option:",                                        # 1
    "    def __init__(self, show_envvar=False):",           # 2
    "        self.show_envvar = show_envvar",                # 3
    "    def get_help_record(self):",                        # 4
    "        if self.show_envvar: pass",                     # 5
    "    def get_help_extra(self):",                         # 6
    "        if self.show_envvar: pass",                     # 7
    "    def unrelated(self):",                              # 8
    "        return 1",                                      # 9
])


def repo(tmp_path) -> Store:
    store = Store(tmp_path)
    store.files.upsert("core.py", "sha", "", None)
    store.symbols.insert([
        Symbol(file="core.py", name="Option.__init__", kind="method", line=2,
               end_line=3, signature=None, decorators=(), doc=None),
        Symbol(file="core.py", name="Option.get_help_record", kind="method", line=4,
               end_line=5, signature=None, decorators=(), doc=None),
        Symbol(file="core.py", name="Option.get_help_extra", kind="method", line=6,
               end_line=7, signature=None, decorators=(), doc=None),
        Symbol(file="core.py", name="Option.unrelated", kind="method", line=8,
               end_line=9, signature=None, decorators=(), doc=None),
    ])
    store.chunks.insert([Chunk(file="core.py", kind="class", name="Option", part=None,
                               start_line=1, end_line=9, text=BODY,
                               breadcrumb="core.py")], None)
    return store


def test_EVERY_symbol_mentioning_the_identifier_is_found(tmp_path) -> None:
    """The measured miss: three sites touch `show_envvar`, and a render that
    names two of them is worse than the grep it replaces."""
    with repo(tmp_path) as store:
        found = mentioned_sites(store, "add show_envvar_value beside show_envvar")
    names = {symbol for _, symbol, _, _ in found}
    assert names == {"Option.__init__", "Option.get_help_record",
                     "Option.get_help_extra"}


def test_a_symbol_that_does_NOT_mention_it_is_left_out(tmp_path) -> None:
    """Completeness over the identifier, not over the file."""
    with repo(tmp_path) as store:
        found = mentioned_sites(store, "add show_envvar_value beside show_envvar")
    assert "Option.unrelated" not in {symbol for _, symbol, _, _ in found}


def test_the_LINE_RANGE_comes_from_the_index(tmp_path) -> None:
    with repo(tmp_path) as store:
        found = mentioned_sites(store, "show_envvar")
    ranges = {symbol: (low, high) for _, symbol, low, high in found}
    assert ranges["Option.get_help_extra"] == (6, 7)


def test_a_COMMON_word_is_not_an_identifier_to_chase(tmp_path) -> None:
    """A task is a sentence. Matching `value` or `help` against a repository
    returns the repository, which is the noise this render exists to avoid."""
    with repo(tmp_path) as store:
        assert mentioned_sites(store, "show the value in the help output") == []


def test_an_identifier_the_repo_never_mentions_finds_nothing(tmp_path) -> None:
    with repo(tmp_path) as store:
        assert mentioned_sites(store, "add frobnicate_widget support") == []


def test_a_markdown_HEADING_never_becomes_a_site(tmp_path) -> None:
    """MEASURED, and it silenced the whole lane. A heading is a symbol whose span
    runs to the end of the document, so `CHANGES.md` contributed 29 rows at
    L1-1630 each — 48 sites total, past MAX_SPREAD, and the lane returned nothing
    while holding the one row that mattered."""
    with repo(tmp_path) as store:
        store.files.upsert("CHANGES.md", "sha", "", None)
        store.symbols.insert([
            Symbol(file="CHANGES.md", name=f"Version 8.{n}.0", kind="h2", line=n,
                   end_line=1630, signature=None, decorators=(), doc=None)
            for n in range(1, 30)])
        store.chunks.insert([Chunk(file="CHANGES.md", kind="section", name=None,
                                   part=None, start_line=1, end_line=1630,
                                   text="show_envvar was added", breadcrumb="c")], None)
        found = mentioned_sites(store, "add show_envvar_value beside show_envvar")
    assert not any(path == "CHANGES.md" for path, _, _, _ in found)
    assert {s for _, s, _, _ in found} == {"Option.__init__",
                                           "Option.get_help_record",
                                           "Option.get_help_extra"}


def test_a_ONE_WORD_name_the_repo_DECLARES_is_chased(tmp_path) -> None:
    """MEASURED on express, and the bias tracked language. Asked to "add
    res.inline beside res.attachment", the lane chased only
    `contentDisposition`: `attachment` is ten characters of one lowercase word,
    so a shape rule wanting snake_case or camelCase rejected the task's most
    important name — while the index has it at `lib/response.js:606`. One-word
    names are the norm in JS and Ruby and the exception in Python, so judging by
    SHAPE was a preference for Python dressed up as a heuristic. The index
    decides instead: it declares `attachment` and has never heard of `beside`.
    """
    with repo(tmp_path) as store:
        store.files.upsert("lib/response.js", "sha", "", None)
        store.symbols.insert([
            Symbol(file="lib/response.js", name="res.attachment", kind="method",
                   line=1, end_line=2, signature=None, decorators=(), doc=None)])
        store.chunks.insert([Chunk(file="lib/response.js", kind="method",
                                   name="res.attachment", part=None, start_line=1,
                                   end_line=2, text="res.attachment = function () {}",
                                   breadcrumb="r")], None)
        found = mentioned_sites(store, "add res.inline beside res.attachment")
    assert ("lib/response.js", "res.attachment", 1, 2) in found


def test_a_nested_closure_is_not_a_second_site(tmp_path) -> None:
    """`test_show_envvar.cmd` at L759-762 lives inside `test_show_envvar` at
    L758-766. Listing both points twice at one edit."""
    with repo(tmp_path) as store:
        store.symbols.insert([
            Symbol(file="core.py", name="Option.get_help_extra.inner", kind="function",
                   line=7, end_line=7, signature=None, decorators=(), doc=None)])
        found = mentioned_sites(store, "show_envvar")
    assert "Option.get_help_extra.inner" not in {s for _, s, _, _ in found}
