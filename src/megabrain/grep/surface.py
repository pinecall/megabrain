"""The names a file already has in scope, as one line of metadata.

MEASURED, and it was the single biggest cost in the run `grep` won. Handed
correct rows for every site, the reader still spent three of its twenty calls on
"is this name already imported here?": one Read to check `os`, one to check
`mock` — and because the answer to the second was NO, one Edit that had to be
undone and rewritten. Its own answer to what would have helped most: "tell me
each listed file's import surface."

Metadata, not code. A line of bound names costs almost nothing and does not
break the rule `grep` exists for — that it never pastes a body, because the
caller's editor is about to open the file anyway.

Read from the PREAMBLE only. A local `import json` inside one function is not
the file's surface, and reporting it would answer for code that cannot see it.
"""

from __future__ import annotations

import re

from ..storage import Store
from ..storage.lines import lines_of

__all__ = ["import_surface", "MAX_NAMES"]

MAX_NAMES = 24
"""Bound names listed per file. Past this the line is longer than the Read it
saves, and a file importing more than two dozen names is telling the reader
about its neighbours rather than about itself."""

_IMPORT = re.compile(r"^\s*(?:from\s+([\w.]+)\s+)?import\s+(.+?)\s*$")
_TRAILING = re.compile(r"\s*#.*$")


def import_surface(store: Store, path: str) -> str:
    """`"os, t, _, ParamType"` — what this file's preamble bound, or "".

    Bound NAMES rather than modules: the reader is asking "can I write `t` here",
    and `import typing as t` answers that while the word `typing` does not.
    """
    names: list[str] = []
    for line in _preamble(store, path):
        match = _IMPORT.match(line)
        if match:
            names.extend(n for n in _bound(match.group(2)) if n not in names)
    return ", ".join(names[:MAX_NAMES])


def _preamble(store: Store, path: str) -> list[str]:
    """Lines up to the first top-level declaration.

    Indentation is the test, because it is the one that holds in every language
    this indexes: an `import` inside a function is indented, a file's own surface
    is not.
    """
    out: list[str] = []
    for line in lines_of(store, path):
        stripped = line.strip()
        if stripped.startswith(("def ", "class ", "async def ")):
            break
        if not line.startswith((" ", "\t")):
            out.append(line)
    return out


def _bound(clause: str) -> list[str]:
    """The names an import clause makes usable: `a as b, c` -> ['b', 'c']."""
    names: list[str] = []
    for part in _TRAILING.sub("", clause).strip("()").split(","):
        piece = part.strip()
        if not piece or piece == "*":
            continue
        # `x as y` binds y; a dotted `a.b` is used as `a`, which is what a
        # caller writes at the call site.
        alias = piece.split(" as ")
        names.append(alias[-1].strip() if len(alias) > 1
                     else piece.split(".")[0].strip())
    return names
