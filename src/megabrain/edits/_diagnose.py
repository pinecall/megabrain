"""Why a `find` did not match, in enough detail to fix it without a re-read.

Split from applying because it is a different job, and the one that decides
whether a failed batch costs the caller one turn or three. A refusal that says
only "not found" sends them back to read the file; a refusal that shows the
line they nearly typed is a correction they can make from where they stand.
"""

from __future__ import annotations

import difflib

__all__ = ["mismatch"]

_CLOSE_ENOUGH = 0.5
"""How similar a real line must be to be worth naming.

Above this it is the line they meant with a typo in it; below, naming it would
send them at something unrelated with false confidence."""


def mismatch(text: str, find: str, found: int, wanted: int) -> str:
    """The error for an op whose `find` matched the wrong number of times.

    The two failures need opposite advice: nothing matched means the string is
    wrong, and too much matched means it is not specific enough.
    """
    tail = (_nearest(text, find) if found == 0 else
            " Add surrounding lines to make it unique, or pass count.")
    return f"find occurs {found} time(s), expected {wanted}.{tail}"


def _nearest(text: str, find: str) -> str:
    """The closest real line to a `find` that matched nothing.

    The typo is usually whitespace or one identifier off. Compared stripped, so
    an indentation mismatch — the single most common cause — still finds its
    line, and reported with the true number so the caller can look at it.
    """
    probe = next((line.strip() for line in find.splitlines() if line.strip()), "")
    lines = text.splitlines()
    close = difflib.get_close_matches(probe, [ln.strip() for ln in lines],
                                      1, _CLOSE_ENOUGH)
    if not probe or not close:
        return ""
    for number, line in enumerate(lines, start=1):
        if line.strip() == close[0]:
            return f" Nearest line: L{number} {line.strip()[:80]!r}"
    return ""
