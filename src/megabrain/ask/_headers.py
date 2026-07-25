"""The preamble of a test file the change adds a test to.

MEASURED, and it is where the last four wasted calls went. Handed a correct
surface for a two-file change, an agent still ran `grep -n "fifo"`, `grep -n
"write_tool"` and two Reads of the test file — using grep it had been told not
to, which is itself the signal that what it was given was not enough.

What it was looking for was not the mechanism. It was whether the symbol it
needed was already imported, and how this file spells a platform skip. Writing
a test needs something writing a function does not: the file's own preamble.

Deterministic and free — the imports are lines in the index, so this is a
citation, not a model call. Bounded by the first declaration, because
everything above it IS the preamble and nothing below it is.
"""

from __future__ import annotations

from ..retrieval.paths import is_test
from ..storage import Store

__all__ = ["test_preambles", "MAX_PREAMBLE_LINES"]

MAX_PREAMBLE_LINES = 60
"""Cap on a preamble, for the file whose imports run to a hundred lines. Past
this the tail is fixtures, not imports, and the reader has the file."""


def test_preambles(store: Store, files: list[str]) -> str:
    """The import block of each TEST file among `files`, as a citation.

    Only tests: production code is reached through the symbols the map already
    lists, while a test is written by imitation and needs to know what its file
    already has in scope.
    """
    sections = []
    for relpath in dict.fromkeys(f for f in files if is_test(f)):
        end = _first_declaration(store, relpath)
        if end > 1:
            sections.append(f"\n\n## {relpath} — what is already imported\n"
                            f"[[{relpath}:1-{min(end - 1, MAX_PREAMBLE_LINES)}]]")
    return "".join(sections)


def _first_declaration(store: Store, relpath: str) -> int:
    """The line the first symbol is declared on — where the preamble ends.

    From the symbol table rather than by scanning for `import`: a preamble is
    not only imports (constants, markers, a module docstring) and every
    language spells them differently, while "before anything is declared" is
    the same sentence everywhere.
    """
    lines = [int(s["line"]) for s in store.symbols.read_for(relpath)
             if isinstance(s.get("line"), int)]
    return min(lines) if lines else 0
