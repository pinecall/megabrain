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
