"""The edit surface, turned into operations `megabrain_replace` can apply.

The engine supplies the half it can be exactly right about — which file, which
lines, and the anchor text VERBATIM from the index — and leaves a hole where
the caller's own code goes. `find` is never typed by a model, so an edit can
never fail on a mistyped anchor; and the code is never written by this engine,
so an edit can never carry a mistake this engine had no way to check.

That division is measured, not tidy-minded. When the engine did author the
code, it produced a guard placed AFTER the write it was guarding, inside an
unclosed `try:`, and the agent spent four retrieval calls and two reads undoing
it — finishing slower than the arm with no megabrain at all. On an easier
change the same mechanism had cut 11 turns to 5. Nobody can tell in advance
which of the two a task is, which is what made it unusable as a default.
"""

from __future__ import annotations

import re

from ..contracts.edits import NEW_CODE
from ..storage import Store
from ._quote import lines_of

__all__ = ["operations_from", "APPLY"]

# [[path:lo-hi]] followed by APPLY <mode>. No fenced block: the model marks
# WHERE the change goes and describes it in prose, and writing it is the
# caller's job.
APPLY = re.compile(
    r"\[\[([^\]:]+):(\d+)-(\d+)\]\]\s*\n\s*"
    r"APPLY\s+(insert_after|insert_before|replace_span)\b")


def operations_from(surface: str, store: Store) -> list[dict[str, str]]:
    """Every marked edit in `surface`, as {file, find, replace} with a hole.

    Silent about what it cannot build: a marker whose range is not real yields
    no operation. A wrong operation would be worse than none — it edits.
    """
    operations: list[dict[str, str]] = []
    for path, start, end, mode in APPLY.findall(surface):
        anchor = _span(store, path.strip(), int(start), int(end))
        if not anchor:
            continue
        operations.append({
            "file": path.strip(),
            "find": anchor,
            # The anchor is repeated into `replace` on an insert so the caller
            # never retypes it either — they fill the hole and nothing else.
            "replace": _placed(anchor, mode),
        })
    return operations


def _placed(anchor: str, mode: str) -> str:
    """Where the hole sits relative to the anchor.

    `insert_before` exists because its absence produced a wrong edit. Guarding
    an operation means adding code BEFORE the thing it guards, and with only
    `insert_after` the model cited the whole function body and said "after" —
    which puts the guard after the write it was supposed to prevent. The prose
    said "before" and the marker said "after"; the mode it needed did not
    exist.
    """
    if mode == "insert_before":
        return f"{NEW_CODE}\n{anchor}"
    if mode == "insert_after":
        return f"{anchor}\n{NEW_CODE}"
    return NEW_CODE


def _span(store: Store, path: str, lo: int, hi: int) -> str:
    """The cited lines, verbatim from the index, or "" if the range is unreal."""
    lines = lines_of(store, path)
    if not lines or lo < 1 or hi < lo or hi > len(lines):
        return ""
    return "\n".join(lines[lo - 1:hi])
