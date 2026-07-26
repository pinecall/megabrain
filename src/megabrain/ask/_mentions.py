"""Every symbol that literally mentions an identifier the TASK named.

MEASURED head to head, and this is the lane that lost it. Asked to add
`show_envvar_value` beside the existing `show_envvar`, a plain `grep show_envvar`
returned all six sites in one call; the model named two, and one it dropped was
where the logic goes (`get_help_extra`). Reordered slightly, that miss ships a
flag that never fires.

A tool that replaces grep must return at least what grep returns, so
completeness is COMPUTED rather than asked for: identifiers from the task,
matched literally, resolved to the symbols containing them. The model still
contributes what grep cannot — the site whose text mentions nothing.

Resolved ONE identifier at a time, which is what lets a broad name be discarded
without taking the specific ones with it — see `_spread`.
"""

from __future__ import annotations

import re

from ..retrieval.paths import is_test
from ..storage import Store
from ._idents import identifiers, outermost
from ._spans import site_at
from ._spread import MAX_ROWS, MAX_SPREAD, merged

__all__ = ["mentioned_sites", "MAX_SPREAD", "MAX_ROWS"]

Site = tuple[str, str, int, int]


def mentioned_sites(store: Store, task: str) -> list[Site]:
    """`(path, symbol, low, high)` for every symbol whose body names one.

    The identifiers come from the task itself, so this is the literal search a
    caller would have run by hand — with the match resolved to the symbol that
    contains it, which is the part a grep cannot do.

    The repo's own symbol names decide which of the task's words are code, so a
    one-word name like `attachment` is chased in JS exactly as `show_envvar` is
    in Python. See `identifiers`: judging that by SHAPE quietly favoured
    snake_case and dropped the JS name the task cared most about.
    """
    wanted = identifiers(task, store.symbols.name_counts())
    if not wanted:
        return []
    texts = [(meta.file, meta.text or "", meta.start_line)
             for meta in store.chunks.read_metas()]
    declared: dict[str, list[dict[str, object]]] = {}
    return merged({name: _for_one(store, name, texts, declared) for name in wanted})


def _for_one(store: Store, name: str, texts: list[tuple[str, str, int]],
             declared: dict[str, list[dict[str, object]]]
             ) -> list[tuple[Site, bool]]:
    """The sites of a SINGLE identifier, read from the chunk text.

    Read from the text rather than from a symbol name match: the identifier is
    being USED at these sites, not declared, which is exactly why a name lookup
    finds the declaration and misses the five places that touch it.

    `declared` caches each file's symbols across identifiers — the walk is once
    per name now, and re-reading them per name made a five-name task five
    queries deep for no new information.

    Each site is paired with whether it is a TEST, which is what lets `_spread`
    serve all of the implementation and only a sample of the suite.
    """
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    found: dict[str, list[tuple[str, int, int]]] = {}
    tests: set[Site] = set()
    for path, text, start in texts:
        if not pattern.search(text):
            continue
        touched = {start + offset for offset, line in enumerate(text.split("\n"))
                   if pattern.search(line)}
        if path not in declared:
            declared[path] = list(store.symbols.read_for(path))
        # A pytest `def test_x()` is a function to the grammar and a test case to
        # the reader, so the PATH decides as well as the kind. Without it the
        # quota was a JS-only rule: Python suites counted as implementation, and
        # a thorough one would empty the lane exactly as express's used to.
        suite = is_test(path)
        for entry in declared[path]:
            row = site_at(entry, touched)
            if row and row not in found.setdefault(path, []):
                found[path].append(row)
                if suite or str(entry.get("kind") or "") == "test":
                    tests.add((path, *row))
    return [((path, symbol, low, high), (path, symbol, low, high) in tests)
            for path, symbols in found.items()
            for symbol, low, high in outermost(symbols)]
