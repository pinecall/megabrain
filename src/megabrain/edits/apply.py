"""Transactional exact-string edits: validate everything, then write.

The write half of the read→edit loop, and it exists on arithmetic: the host's
Edit requires a prior host Read of the SAME file, so every body megabrain
already rendered gets paid for twice.

Two phases, and the order is the contract. Every op is validated in memory
against the EVOLVING text — so a batch may edit a line and then edit what it
just wrote — and only if all pass does anything reach disk. A half-applied
batch is the one outcome a caller cannot recover from: they cannot see which
half.

The engine never invents content: `find` and `replace` are the caller's own
strings, applied verbatim — the narrator's anti-hallucination stance, on the
write side.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from ..contracts.edits import EditResult, EditRow
from ._diagnose import mismatch
from ._fields import FILE, FIND, REPLACE, field, safe_path
from ._syntax import refuse_if_broken

__all__ = ["apply_edits"]


def apply_edits(root: Path | str, operations: Sequence[Mapping[str, Any]]) -> EditResult:
    """Apply every op or none. Never raises for a failure a caller expects."""
    root = Path(root)
    texts: dict[str, str] = {}
    report = [_stage(root, op, number, texts)
              for number, op in enumerate(operations, start=1)]
    refuse_if_broken(root, report, texts)
    if any("error" in row for row in report):
        return EditResult(ok=False, report=report, written=[])
    written = sorted(texts)
    for relpath in written:
        safe_path(root, relpath).write_text(texts[relpath], encoding="utf-8")
    return EditResult(ok=True, report=report, written=written)


def _stage(root: Path, op: Mapping[str, Any], number: int,
           texts: dict[str, str]) -> EditRow:
    """Validate one op against the pending text, applying it to `texts` on
    success. Returns the row either way — a failure is a result, not a raise."""
    relpath = field(op, *FILE)
    row = EditRow(op=number, file=relpath)
    if not relpath:
        row["error"] = ("missing 'file'. Each operation is "
                        "{file, find, replace, count?}.")
        return row
    if (problem := _load(root, relpath, texts)) is not None:
        row["error"] = problem
        return row
    find, wanted = field(op, *FIND), _count(op)
    if not find:
        # `"".count("")` is not zero and `replace("", x)` rewrites every gap in
        # the file, so an empty find would PASS validation and destroy the text.
        row["error"] = "empty find"
        return row
    found = texts[relpath].count(find)
    if found != wanted:
        row["error"] = mismatch(texts[relpath], find, found, wanted)
        return row
    texts[relpath] = texts[relpath].replace(find, field(op, *REPLACE))
    row["replaced"] = wanted
    return row


def _load(root: Path, relpath: str, texts: dict[str, str]) -> str | None:
    """Read the file into the pending set, or say why not."""
    if relpath in texts:
        return None
    try:
        target = safe_path(root, relpath)
    except ValueError as escape:
        return str(escape)
    if not target.is_file():
        return (f"no such file: {relpath} — replace edits files that exist; "
                "use the host's Write to create one")
    texts[relpath] = target.read_text(encoding="utf-8")
    return None


def _count(op: Mapping[str, Any]) -> int:
    try:
        return max(1, int(op.get("count", 1)))
    except (TypeError, ValueError):
        return 1
