"""What the edit SITES themselves reference — the last file a grep cannot reach.

MEASURED, and it is the row that survived two rounds of fixing. Adding
`show_envvar_value` to click needs a key added to the `OptionHelpExtra` TypedDict
in ANOTHER file, and no literal search can find it: its body never contains the
string `show_envvar`. The plain-grep arm needed a separate search for it, and
paid four calls groping around.

But the site that must change, `Option.get_help_extra`, is declared
`-> types.OptionHelpExtra` — so the index HAS the link. One hop out from each
site, resolved by the same uniqueness rule the navigator uses, reaches the file
neither grep nor the model named.
"""

from __future__ import annotations

from megabrain.chunkers.model import Chunk, Symbol
from megabrain.grep.referenced import referenced_sites
from megabrain.storage import Store

CORE = "\n".join([
    "def get_help_extra(self) -> types.OptionHelpExtra:",   # 1
    "    extra: types.OptionHelpExtra = {}",                # 2
    "    return extra",                                     # 3
])
TYPES = "class OptionHelpExtra(TypedDict):\n    envvars: str\n"


def repo(tmp_path) -> Store:
    store = Store(tmp_path)
    for path in ("core.py", "types.py"):
        store.files.upsert(path, "sha", "", None)
    store.symbols.insert([
        Symbol(file="core.py", name="Option.get_help_extra", kind="method", line=1,
               end_line=3, signature=None, decorators=(), doc=None),
        Symbol(file="types.py", name="OptionHelpExtra", kind="class", line=1,
               end_line=2, signature=None, decorators=(), doc=None),
    ])
    store.chunks.insert([
        Chunk(file="core.py", kind="method", name="get_help_extra", part=None,
              start_line=1, end_line=3, text=CORE, breadcrumb="core.py"),
        Chunk(file="types.py", kind="class", name="OptionHelpExtra", part=None,
              start_line=1, end_line=2, text=TYPES, breadcrumb="types.py"),
    ], None)
    return store


SITES = [("core.py", "Option.get_help_extra", 1, 3)]


def test_the_TYPE_a_site_declares_is_reached(tmp_path) -> None:
    """The measured survivor: a second file, named only in the site's signature,
    that a literal search for the task's identifiers can never find."""
    with repo(tmp_path) as store:
        found = referenced_sites(store, SITES)
    assert ("types.py", "OptionHelpExtra", 1, 2) in found


def test_a_site_ALREADY_listed_is_not_repeated(tmp_path) -> None:
    """One hop out, not a second copy of where we started."""
    with repo(tmp_path) as store:
        found = referenced_sites(store, SITES)
    assert not any(name == "Option.get_help_extra" for _, name, _, _ in found)


def test_an_AMBIGUOUS_name_is_not_followed(tmp_path) -> None:
    """Two files declaring it makes the jump a guess, and the navigator's rule
    applies: a link that could land anywhere is worse than no link."""
    with repo(tmp_path) as store:
        store.files.upsert("other.py", "sha", "", None)
        store.symbols.insert([
            Symbol(file="other.py", name="OptionHelpExtra", kind="class", line=9,
                   end_line=10, signature=None, decorators=(), doc=None)])
        assert referenced_sites(store, SITES) == []


def test_it_does_not_hop_TWICE(tmp_path) -> None:
    """One hop. Following what the referenced file references in turn walks the
    repository, which is the render this exists inside of avoiding."""
    with repo(tmp_path) as store:
        store.files.upsert("deep.py", "sha", "", None)
        store.symbols.insert([
            Symbol(file="deep.py", name="TypedDictBase", kind="class", line=1,
                   end_line=2, signature=None, decorators=(), doc=None)])
        store.chunks.insert([Chunk(file="deep.py", kind="class", name="TypedDictBase",
                                   part=None, start_line=1, end_line=2,
                                   text="class TypedDictBase: pass",
                                   breadcrumb="deep.py")], None)
        found = referenced_sites(store, SITES)
    assert not any(name == "TypedDictBase" for _, name, _, _ in found)


def test_no_sites_means_no_hops(tmp_path) -> None:
    with repo(tmp_path) as store:
        assert referenced_sites(store, []) == []


def test_a_same_file_helper_OUTSIDE_the_shown_spans_is_a_row(tmp_path) -> None:
    """MEASURED on rails#52478. The map named `assert_enqueued_with` L436-482;
    the behaviour lived in `prepare_args_for_assertion`, a private helper the
    site CALLS, 300 lines below in the same 800-line file — and the same-file
    rule dropped it ("the reader is already there"). The reader is pointed at
    a LINE RANGE, not a file: a helper outside every shown span is as
    invisible as another file, and re-finding it cost the agent three calls.
    """
    body = "def assert_enqueued_with(job):\n    prepare_args_for_assertion(job)\n"
    helper = "def prepare_args_for_assertion(args):\n    return args\n"
    with Store(tmp_path) as store:
        store.files.upsert("test_helper.py", "sha", "", None)
        store.symbols.insert([
            Symbol(file="test_helper.py", name="assert_enqueued_with", kind="function",
                   line=1, end_line=2, signature=None, decorators=(), doc=None),
            Symbol(file="test_helper.py", name="prepare_args_for_assertion",
                   kind="function", line=400, end_line=402, signature=None,
                   decorators=(), doc=None),
        ])
        store.chunks.insert([
            Chunk(file="test_helper.py", kind="function", name="assert_enqueued_with",
                  part=None, start_line=1, end_line=2, text=body,
                  breadcrumb="test_helper.py"),
            Chunk(file="test_helper.py", kind="function",
                  name="prepare_args_for_assertion", part=None, start_line=400,
                  end_line=402, text=helper, breadcrumb="test_helper.py"),
        ], None)
        found = referenced_sites(
            store, [("test_helper.py", "assert_enqueued_with", 1, 2)])
    assert ("test_helper.py", "prepare_args_for_assertion", 400, 402) in found


def test_a_same_file_helper_INSIDE_a_shown_span_stays_dropped(tmp_path) -> None:
    """The original rule's true half: a helper the reader is already looking
    at is not a second place to go."""
    body = ("def outer():\n    inner()\n\n"
            "def inner():\n    return 1\n")
    with Store(tmp_path) as store:
        store.files.upsert("mod.py", "sha", "", None)
        store.symbols.insert([
            Symbol(file="mod.py", name="outer", kind="function", line=1,
                   end_line=2, signature=None, decorators=(), doc=None),
            Symbol(file="mod.py", name="inner", kind="function", line=4,
                   end_line=5, signature=None, decorators=(), doc=None),
        ])
        store.chunks.insert([
            Chunk(file="mod.py", kind="module", name="mod", part=None,
                  start_line=1, end_line=5, text=body, breadcrumb="mod.py"),
        ], None)
        # The map already shows L1-5 of this file: inner lives inside it.
        found = referenced_sites(store, [("mod.py", "mod", 1, 5)])
    assert ("mod.py", "inner", 4, 5) not in found


def test_the_cap_is_shared_round_robin_not_first_come(tmp_path) -> None:
    """MEASURED on rails#52478, end to end: the lane found
    `prepare_args_for_assertion` when run over its site alone — and the full
    map never showed it, because sites from files EARLIER in the map had
    already spent all `MAX_REFERENCED` rows. A cap consumed in map order
    starves exactly the site the reader asked about; one reference per site
    per round keeps the cap and spreads it.
    """
    hoarder = "def hoarder():\n    " + "\n    ".join(
        f"helper_number_{n}()" for n in range(8)) + "\n"
    starved = "def starved():\n    the_one_that_matters()\n"
    with Store(tmp_path) as store:
        for path in ("a.py", "b.py", "lib.py"):
            store.files.upsert(path, "sha", "", None)
        symbols = [Symbol(file="lib.py", name=f"helper_number_{n}", kind="function",
                          line=10 + n * 3, end_line=11 + n * 3, signature=None,
                          decorators=(), doc=None) for n in range(8)]
        symbols += [
            Symbol(file="a.py", name="hoarder", kind="function", line=1,
                   end_line=9, signature=None, decorators=(), doc=None),
            Symbol(file="b.py", name="starved", kind="function", line=1,
                   end_line=2, signature=None, decorators=(), doc=None),
            Symbol(file="lib.py", name="the_one_that_matters", kind="function",
                   line=90, end_line=92, signature=None, decorators=(), doc=None),
        ]
        store.symbols.insert(symbols)
        store.chunks.insert([
            Chunk(file="a.py", kind="function", name="hoarder", part=None,
                  start_line=1, end_line=9, text=hoarder, breadcrumb="a.py"),
            Chunk(file="b.py", kind="function", name="starved", part=None,
                  start_line=1, end_line=2, text=starved, breadcrumb="b.py"),
        ], None)
        found = referenced_sites(store, [("a.py", "hoarder", 1, 9),
                                         ("b.py", "starved", 1, 2)])
    assert len(found) <= 6
    assert ("lib.py", "the_one_that_matters", 90, 92) in found, \
        "the second site's one reference must survive the first site's eight"


def test_within_a_site_references_come_in_READING_order(tmp_path) -> None:
    """`identifiers()` returns a set, so which of a site's references won the
    round-robin slot was a hash accident. The body's own order is the ranking
    the reader would build: what the site touches first, first."""
    body = ("def site():\n"
            "    first_thing_it_calls()\n"
            "    second_thing_it_calls()\n"
            "    third_thing_it_calls()\n")
    with Store(tmp_path) as store:
        for path in ("a.py", "lib.py"):
            store.files.upsert(path, "sha", "", None)
        store.symbols.insert([
            Symbol(file="a.py", name="site", kind="function", line=1,
                   end_line=4, signature=None, decorators=(), doc=None),
            Symbol(file="lib.py", name="first_thing_it_calls", kind="function",
                   line=10, end_line=11, signature=None, decorators=(), doc=None),
            Symbol(file="lib.py", name="second_thing_it_calls", kind="function",
                   line=20, end_line=21, signature=None, decorators=(), doc=None),
            Symbol(file="lib.py", name="third_thing_it_calls", kind="function",
                   line=30, end_line=31, signature=None, decorators=(), doc=None),
        ])
        store.chunks.insert([Chunk(file="a.py", kind="function", name="site",
                                   part=None, start_line=1, end_line=4, text=body,
                                   breadcrumb="a.py")], None)
        found = referenced_sites(store, [("a.py", "site", 1, 4)])
    assert found[0] == ("lib.py", "first_thing_it_calls", 10, 11)
    assert found[1] == ("lib.py", "second_thing_it_calls", 20, 21)
