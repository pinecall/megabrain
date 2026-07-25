"""How to choose an anchor — the half of the prompt about ADDRESSES.

Split from the shape of the answer because they fail differently. A wrong
shape produces something unparseable that is obvious at a glance; a wrong
anchor produces a valid-looking edit in the wrong place, which is what a guard
landing after the write it guarded looked like.
"""

from __future__ import annotations

__all__ = ["ANCHOR_RULES"]

ANCHOR_RULES = """The citation is an ANCHOR as well as a quotation: the engine reads those exact \
lines out of the index and builds the edit from them. Cite the SMALLEST span \
that is unique in the file — a few lines, never a whole function body — and \
sitting exactly where the change meets it. Three modes:

  APPLY insert_after    the new code goes AFTER the cited lines
  APPLY insert_before   the new code goes BEFORE them
  APPLY replace_span    the cited lines are REPLACED by the new code

Pick the one that makes the anchor SMALL and adjacent. A guard goes BEFORE the \
statement it guards, so cite that statement and say `insert_before` — citing \
the whole function and saying `insert_after` puts the guard after the thing it \
was meant to prevent, which is a bug that reads as correct.

On an `insert_after`, the anchor's LAST LINE is the insertion point: the new \
code lands inside whatever block that line is inside. Never end such an anchor \
on a line that CLOSES the block the change belongs in — an anchor ending on the \
`end`/`}`/`)` of a class, describe or function puts the change outside it."""
