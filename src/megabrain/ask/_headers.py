"""The preamble of a test file the change adds a test to.

MEASURED three times, and the last one was a LANGUAGE bug. Handed a correct
surface, an agent still grepped and read the test file twice to learn whether
the symbol it needed was already imported, and how the file spells a platform
skip. Writing a test needs something writing a function does not: the file's own
preamble. Deterministic and free — the imports are lines in the index, so this
is a citation, not a model call.

Read from the CITATIONS, not from a list of files the caller assembled: it used
to take the files of the prepared operations, and when one was dropped the
preamble silently vanished with it and the agent guessed the imports instead.

And bounded by the first SUBSTANTIAL declaration, not the first declaration of
any kind. In Python the imports are not symbols, so "everything above the first
symbol" was the preamble. In JavaScript `const express = require('../')` IS a
symbol — so on express the section promised the imports and delivered
`'use strict'` and a blank line, cutting at line 2 the very lines it exists to
show. The reader had to open the file to learn that the repo requires `'../'`
rather than `'express'`, a local convention nothing else would have revealed.
"""

from __future__ import annotations

from ..retrieval.paths import is_test
from ..storage import Store
from ._quote import CITATION, lines_of

__all__ = ["already_imported", "MAX_PREAMBLE_LINES"]

MAX_PREAMBLE_LINES = 60
"""Cap on a preamble, for the file whose imports run to a hundred lines. Past
this the tail is fixtures, not imports, and the reader has the file."""

_BINDINGS = {"constant", "const", "var", "let", "import", "variable"}
"""Kinds a module-level BINDING can carry across the languages indexed here.

A binding at the top of a file is part of the preamble — in most languages that
IS the import — so the preamble runs THROUGH them and stops at the first
function, class or block."""


def already_imported(store: Store, surface: str) -> str:
    """The import block of each TEST file cited in `surface`, as a citation.

    NOT named for the word "test": pytest collects any module-level callable
    whose name starts with `test`, so a `test_preambles` imported into a test
    file is run AS a test and errors on a missing `store` fixture.
    """
    cited = dict.fromkeys(path.strip() for path, _, _ in CITATION.findall(surface))
    sections = []
    for relpath in (path for path in cited if is_test(path)):
        end = _preamble_end(store, relpath)
        if end >= 1:
            sections.append(f"\n\n## {relpath} — what is already imported\n"
                            f"[[{relpath}:1-{min(end, MAX_PREAMBLE_LINES)}]]")
    return "".join(sections)


def _preamble_end(store: Store, relpath: str) -> int:
    """The last line of the preamble: everything before the file's real work.

    Bindings are passed THROUGH (they are the imports), then the run is extended
    over the non-blank lines that follow — an `import` or `require` the chunker
    did not record as a symbol still belongs to the block, and a blank line is
    where every language agrees the preamble ended.
    """
    symbols = sorted((s for s in store.symbols.read_for(relpath)
                      if isinstance(s.get("line"), int)),
                     key=lambda s: int(s["line"]))
    end = 0
    for symbol in symbols:
        if str(symbol.get("kind")) not in _BINDINGS:
            return int(symbol["line"]) - 1
        end = max(end, int(symbol.get("end_line") or symbol["line"]))
    return _through_blank(store, relpath, end) if end else 0


def _through_blank(store: Store, relpath: str, start: int) -> int:
    lines = lines_of(store, relpath)
    end = start
    while end < len(lines) and lines[end].strip():
        end += 1
    return end
