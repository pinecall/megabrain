"""The tests that EXERCISE what the change touches — wherever they live.

MEASURED. Asked to make sinatra's `back` refuse a cross-host referer, the
surface showed the tests beside the anchor, the change went in clean, and it
broke `test_makes_redirecting_back_pretty` 1 800 lines further down the SAME
file — a test asserting that `redirect back` sent you to github.com. That test
WAS the bug, pinned, and the agent found it only by running the suite.

Proximity is the wrong relation: a test exercising a symbol can sit anywhere,
and the one that breaks is the one nobody cited. `megabrain_search` has always
promised "the tests that pin the behaviour"; this is that promise, computed
from the pin edges the indexer already built.
"""

from __future__ import annotations

import re

from ...retrieval.paths import is_test
from ...storage import PIN_KIND, Store
from ..citing._codeonly import outside_strings
from ..citing._window import window_around

__all__ = ["exercising_tests", "MAX_PINNED"]

MAX_PINNED = 3
"""Test chunks cited beyond the ones the answer already shows.

Enough for the distant block the change breaks, short of pasting a suite. The
count that mattered was ONE — the block nobody looked at."""

_CITED = re.compile(r"\[\[([^\]:]+):(\d+)-(\d+)\]\]")

_ASSERTS = re.compile(r"\b(assert\w*|expect|should|must_\w+|refute\w*)\b")
"""A chunk that pins behaviour makes a CLAIM about it.

MEASURED as the one section a reader skimmed and discarded: a fixture app under
`test/integration/` surfaced because a route in it is named for the symbol. The
path says test, the content says fixture — a mention is not a pin."""


def exercising_tests(store: Store, surface: str) -> str:
    """Citations for the tests that name a symbol this change touches."""
    cited = _cited(surface)
    names = {name for path, lo, hi in cited
             for name in _symbols_in(store, path, lo, hi)}
    pinning = {test for path, _, _ in cited
               for test in store.graph.sources_of(path, PIN_KIND)}
    if not names or not pinning:
        return ""
    found = [f"[[{path}:{lo}-{hi}]]"
             for path, lo, hi in _chunks_naming(store, names, pinning, cited)]
    if not found:
        return ""
    return ("\n\n## Tests that pin this behaviour — read before changing it\n"
            + "\n".join(found[:MAX_PINNED]))


def _cited(surface: str) -> list[tuple[str, int, int]]:
    return [(path.strip(), int(lo), int(hi))
            for path, lo, hi in _CITED.findall(surface)]


def _symbols_in(store: Store, path: str, lo: int, hi: int) -> set[str]:
    """The bare names declared inside the cited span — what the change alters.

    Bare, because a test writes `back`, never `Sinatra.Helpers.back`.
    """
    return {str(s["name"]).rsplit(".", 1)[-1]
            for s in store.symbols.read_for(path)
            if lo <= s["line"] <= hi}


def _chunks_naming(store: Store, names: set[str], pinning: set[str],
                   cited: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """Chunks naming `names`, inside the tests that PIN the changed file.

    Scoped by the pin edges, not searched repo-wide, and that is not an
    optimisation: `back` is an English word, and matched everywhere it returned
    two rack-protection specs and a helper module — noise that pushed the block
    that actually breaks off the list. A pin is a fact the indexer computed; a
    file that says "back" is a coincidence.

    Skipped by SPAN, never by file — the block that broke sat in the same file,
    1 800 lines below the ones already cited. Ranked by how many changed names
    a chunk mentions.
    """
    wanted = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(names)) + r")\b")
    hits: list[tuple[int, str, int, int]] = []
    for meta in store.chunks.read_metas():
        if meta.file not in pinning or not is_test(meta.file):
            continue
        if any(path == meta.file and lo <= meta.end_line and meta.start_line <= hi
               for path, lo, hi in cited):
            continue                      # already in front of the reader
        matched = set(wanted.findall(outside_strings(meta.text or "")))
        if matched and _ASSERTS.search(meta.text or ""):
            lo, hi = window_around(meta.text or "", meta.start_line, wanted)
            hits.append((len(matched), meta.file, lo, hi))
    return [(f, lo, hi) for _, f, lo, hi in sorted(hits, reverse=True)]
