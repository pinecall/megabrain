"""Assembling what a task answer LOOKS like, as opposed to how it is found.

Split from the loop because the two change for different reasons: the loop is
about conversing with a model until it stops asking for files, and this is
about what the reader gets handed at the end. Both grew, and reading either one
meant scrolling past the other.
"""

from __future__ import annotations

import json

from ..storage import Store
from .tools import open_file

__all__ = ["apply_block", "full_files"]


def full_files(store: Store, operations: list[dict[str, str]]) -> str:
    """Every file the batch touches, whole, when the caller asked for it.

    Opt-in and never inferred. Measured on a real two-file change: the surface
    is ~475 tokens and the same two files whole are ~21 500 — 45 times the
    cost, for something the agent read 125 lines of. The caller is the one who
    knows whether it will review before applying, so the caller says so.

    Scoped to the files the CHANGE touches rather than everything that was
    opened: a file consulted to imitate its style is already quoted in the
    surface, and appending it whole would be paying twice for the pattern.
    """
    parts = []
    for relpath in dict.fromkeys(op["file"] for op in operations):
        parts.append(f"\n\n## {relpath} — in full\n{open_file(store, relpath)}")
    return "".join(parts)


def apply_block(operations: list[dict[str, str]]) -> str:
    """The whole change as ONE `megabrain_replace` batch.

    MEASURED: handed the surface as prose, an agent spent two `replace` calls
    and a `Read` applying a two-file change it had already been given — it
    rebuilt the exact-string operations itself, one file at a time. They are
    built here instead, from the index, so applying the change is one call and
    the `find` strings cannot be mistyped.
    """
    if not operations:
        return ""
    return ("\n\n## Apply — ONE call, all files at once\n"
            "```json\n" + json.dumps({"operations": operations}, indent=2)
            + "\n```\n")
