"""The edit report as text a caller acts on.

Two jobs, and the failing one matters more. On success it says what changed and
points at the NEXT step — an edit is not the end of a task, a green gate is. On
failure it has to make "nothing was written" impossible to misread, because a
caller who believes half the batch landed will go looking for damage that is
not there, or worse, re-run the half that did.
"""

from __future__ import annotations

from ..contracts.edits import EditResult

__all__ = ["render_edits"]


def render_edits(result: EditResult) -> str:
    rows = result["report"]
    if result["ok"]:
        head = (f"# megabrain replace — {len(rows)} op(s) applied, "
                f"{len(result['written'])} file(s) written. Run the gates now.")
        return "\n".join([head] + [
            f"  ok   op {row['op']} {row['file']} — "
            f"{row.get('replaced', 0)} replacement(s)" for row in rows])
    head = "# megabrain replace — FAILED, NOTHING was written (transactional)."
    return "\n".join([head] + [
        f"  {'FAIL' if 'error' in row else 'ok  '} op {row['op']} {row['file']}"
        + (f" — {row['error']}" if "error" in row else "") for row in rows])
