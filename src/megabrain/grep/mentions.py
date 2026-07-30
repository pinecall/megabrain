"""Every symbol that literally mentions an identifier the TASK named.

MEASURED head to head, and this is the lane that lost it: asked to add
`show_envvar_value` beside `show_envvar`, plain grep returned all six sites in
one call; the model named two and dropped the one where the logic goes. So
completeness is COMPUTED rather than asked for — identifiers from the task,
matched literally, resolved to the symbols containing them, one identifier at
a time so a broad name can be discarded without the specific ones (`_spread`).
"""

from __future__ import annotations

import re

from ..search.paths import is_test
from ..storage import Store
from ..storage.rows import SymbolRow
from .idents import identifiers, outermost
from .spans import site_at
from .spread import MAX_ROWS, MAX_SPREAD, merged

__all__ = ["mentioned_sites", "MAX_SPREAD", "MAX_ROWS"]

Site = tuple[str, str, int, int]


def mentioned_sites(store: Store, task: str) -> list[Site]:
    """`(path, symbol, low, high)` for every symbol whose body names one.

    The literal search the caller would have run by hand, with each match
    resolved to its containing symbol — the part grep cannot do. The repo's own
    symbol names decide which task words are code (`identifiers`: judging by
    SHAPE favoured snake_case and dropped the JS name the task cared about).
    """
    wanted = identifiers(task, store.symbols.name_counts())
    if not wanted:
        return []
    texts = [(meta.file, meta.text or "", meta.start_line)
             for meta in store.chunks.read_metas()]
    declared: dict[str, list[SymbolRow]] = {}
    return merged({name: _for_one(store, name, texts, declared) for name in wanted})


def _for_one(store: Store, name: str, texts: list[tuple[str, str, int]],
             declared: dict[str, list[SymbolRow]]
             ) -> list[tuple[Site, bool]]:
    """The sites of a SINGLE identifier, read from the chunk text.

    From the TEXT, not a symbol-name match: the identifier is USED at these
    sites, not declared. `declared` caches each file's symbols across
    identifiers; each site carries whether it is a TEST, which lets `_spread`
    serve all implementation and only a sample of the suite."""
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    found: dict[str, list[tuple[str, int, int]]] = {}
    containers: set[tuple[str, str, int, int]] = set()
    tests: set[Site] = set()
    for path, text, start in texts:
        if not pattern.search(text):
            continue
        touched = {start + offset for offset, line in enumerate(text.split("\n"))
                   if pattern.search(line)}
        if path not in declared:
            declared[path] = list(store.symbols.read_for(path))
        # A pytest `def test_x()` is a function to the grammar and a test to
        # the reader, so the PATH decides as well as the kind — else the quota
        # was a JS-only rule and Python suites counted as implementation.
        suite = is_test(path)
        for entry in declared[path]:
            row = site_at(entry, touched)
            if row and row not in found.setdefault(path, []):
                found[path].append(row)
                if str(entry.get("kind") or "") in ("class", "module"):
                    containers.add((path, *row))
                if suite or str(entry.get("kind") or "") == "test":
                    tests.add((path, *row))
    return [((path, symbol, low, high), (path, symbol, low, high) in tests)
            for path, symbols in found.items()
            for symbol, low, high in outermost(_no_swallowing(path, symbols,
                                                              containers))]


def _no_swallowing(path: str, symbols: list[tuple[str, int, int]],
                   containers: set[tuple[str, str, int, int]]
                   ) -> list[tuple[str, int, int]]:
    """A CONTAINER never beats the declaration inside it.

    `outermost` keeps the outer of two nested rows — right for a closure in a
    test, MEASURED wrong for the wrapper module every Ruby file has: rails'
    `core.rb` wraps 217 lines in `module ActiveJob` (under `MAX_SPAN`), which
    contained every match and swallowed `Core#set` — the origin of the state
    three A/B duels needed and never saw. A container that matched only at its
    own level (a constant, an include) still stands: nothing tighter existed.
    """
    tight = [(a, b) for name, a, b in symbols
             if (path, name, a, b) not in containers]
    return [(name, low, high) for name, low, high in symbols
            if (path, name, low, high) not in containers
            or not any(low <= a and b <= high and (a, b) != (low, high)
                       for a, b in tight)]
