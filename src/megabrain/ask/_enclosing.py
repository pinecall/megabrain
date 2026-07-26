"""The whole function an ANCHOR sits inside — its signature and its exits.

MEASURED, and it is the plainest thing any of these reports has said. Asked to
guard `write`, the surface anchored on `try:` and the line under it; the agent
wrote the guard and then observed that the spec told it to `raise` inside a
`try:` whose `except` clause it had never been shown. Whether that raise
survives to the caller depends entirely on the handler, and the handler was the
one part of the edit site the answer omitted. It hoisted the guard above the
`try:` to reason around the gap — an inference forced, not answered.

Same relation in the other repository: an agent inferred a tool's parameter
names from a four-line anchor, because the signature above it was not quoted.

The anchor stays SMALL, which is what makes it a usable `find`. The function
around it is what makes the edit correct, and the index knows exactly where it
begins and ends.
"""

from __future__ import annotations

import re

from ..storage import Store

__all__ = ["enclosing_bodies", "MAX_ENCLOSING"]

MAX_ENCLOSING = 3
"""Enclosing bodies cited. A change touches two or three sites; past that the
answer is a file listing, and the elision keeps each one bounded anyway."""

_ANCHORED = re.compile(r"\[\[([^\]:]+):(\d+)-(\d+)\]\]\s*\n\s*APPLY\s+\w+")
"""Only citations followed by an APPLY. A quote with no marker is an example to
imitate, and what surrounds an example is not the reader's problem."""

_SPANNING = {"function", "method", "def", "class_method", "instance_method"}
"""Kinds whose body is a unit of behaviour worth reading whole. A `class` is
excluded deliberately: its body is the file, and the measured complaint about
oversized quotes came from exactly that."""


def enclosing_bodies(store: Store, surface: str) -> str:
    """Citations for the function containing each anchor in `surface`."""
    found: list[tuple[str, int, int]] = []
    for path, start, end in _ANCHORED.findall(surface):
        span = _enclosing(store, path.strip(), int(start), int(end))
        if span and span not in found:
            found.append(span)
    if not found:
        return ""
    return ("\n\n## The code you are editing INSIDE — signature and exits\n"
            + "\n".join(f"[[{path}:{lo}-{hi}]]" for path, lo, hi in found[:MAX_ENCLOSING]))


def _enclosing(store: Store, path: str, lo: int, hi: int) -> tuple[str, int, int] | None:
    """The SMALLEST spanning symbol that strictly contains the anchor.

    Strictly: an anchor already covering its whole function needs nothing added,
    and re-citing it would be the duplication a reader named as wasted budget.
    Smallest, because a method inside a class is the unit being edited.
    """
    holders = [s for s in store.symbols.read_for(path)
               if str(s.get("kind")) in _SPANNING
               and isinstance(s.get("line"), int) and isinstance(s.get("end_line"), int)
               and int(s["line"]) <= lo and hi <= int(s["end_line"])
               and not (int(s["line"]) >= lo and int(s["end_line"]) <= hi)]
    if not holders:
        return None
    best = min(holders, key=lambda s: int(s["end_line"]) - int(s["line"]))
    return path, int(best["line"]), int(best["end_line"])
