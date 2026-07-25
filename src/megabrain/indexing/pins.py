"""Which test file PINS which implementation file.

The gap this closes, measured: `sinatra` indexes 162 files and produces **zero**
edges. Ruby, Go, Rust, PHP, C, C++, Java and C# all reach `GrammarStrategy`,
whose `edges()` returns None — so on those repositories the graph does not
exist and retrieval runs on cosine alone. That is the whole reason a real task
("add a redirect_back helper…") cost the same number of turns as `grep`: the
file the change had to edit its test into, `test/helpers_test.rb`, was never in
the bundle, and no ranking tweak could put it there because nothing structural
connected it to `lib/sinatra/base.rb`.

Language-agnostic on purpose: computed from the SYMBOL TABLE, which every
language produces, rather than from any grammar's import syntax. Imports would
not have helped anyway — sinatra's `helpers_test.rb` requires only
`test_helper`, so the chain reaches `base.rb` in three hops no one-hop
neighbour lookup would follow.

The rule against PHANTOM edges is the one `edges.py` rests on, borrowed from
`SymbolTable.name_counts`: only a symbol declared in EXACTLY ONE non-test file
counts. A test naming `get` must not be evidence about every file declaring a
`get` — an edge that could point anywhere hands a reader an unrelated file AS
evidence, which is worse than no edge.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from ..retrieval.paths import is_test
from ..storage import PIN_KIND, Store

__all__ = ["write_pin_edges", "PIN_SCHEMA", "MIN_SHARED"]

PIN_SCHEMA = 1
"""Bumped when the rule changes, so an index built by an older engine rebuilds
its pins instead of keeping a stale relation forever — the same catch-up
`edge_schema` performs for the language extractors."""

MIN_SHARED = 3
"""Unambiguous symbols a test must name before it counts as pinning a file.

One is a mention; three is a test working with something. Measured on sinatra,
the real companions clear it by an order of magnitude — `helpers_test.rb` names
47 of `base.rb`'s unique symbols — so it only has to exclude the incidental."""

# Matches the identifier shape a test would actually write. Three characters
# minimum: shorter names are almost always language keywords or loop variables,
# and they are exactly the ones that collide across a repository.
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


def write_pin_edges(store: Store) -> int:
    """Rebuild every `pins` edge in the repository. Returns edges written.

    A full recompute rather than an incremental one: a pin is a relation
    between two files, so editing EITHER end can create or destroy it, and
    tracking that incrementally would mean invalidating every test whenever any
    implementation file's symbols change. The pass costs no network and no
    embedding — it reads text already in the index.
    """
    store.graph.set_meta("pin_schema", PIN_SCHEMA)
    declared = _unambiguous(store)
    if not declared:
        return 0
    shared: dict[str, Counter[str]] = defaultdict(Counter)
    for relpath, text in store.chunks.read_texts():
        if not is_test(relpath):
            continue
        for token in set(_IDENT.findall(text)):
            target = declared.get(token)
            if target is not None and target != relpath:
                shared[relpath][target] += 1
    store.graph.clear_kind(PIN_KIND)
    written = 0
    for relpath, counts in shared.items():
        pinned = sorted(dst for dst, n in counts.items() if n >= MIN_SHARED)
        store.graph.add_edges(relpath, pinned, PIN_KIND)
        written += len(pinned)
    return written


def _unambiguous(store: Store) -> dict[str, str]:
    """Bare symbol name -> the ONE non-test file declaring it.

    Tests are excluded as declarers: a test helper sharing a name with
    production code would make every other test look like it pins that test.
    """
    owners: dict[str, set[str]] = defaultdict(set)
    for relpath in store.files.all_paths():
        if is_test(relpath):
            continue
        for symbol in store.symbols.read_for(relpath):
            name = symbol.get("name")
            if name:
                owners[str(name).rsplit(".", 1)[-1]].add(relpath)
    return {name: next(iter(files)) for name, files in owners.items()
            if len(files) == 1 and len(name) > 3}
