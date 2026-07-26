"""How to choose an anchor — the half of the prompt about ADDRESSES.

Split from the shape of the answer because they fail differently. A wrong
shape produces something unparseable that is obvious at a glance; a wrong
anchor produces a valid-looking edit in the wrong place, which is what a guard
landing after the write it guarded looked like.

The anchor is the reader's ADDRESS, not an operation this engine builds. It
tried building them, and both measured attempts were wrong in the same way —
the insertion point was a line that opens a block, so the change landed inside
it. What the engine can be exactly right about is which lines those are.
"""

from __future__ import annotations

__all__ = ["ANCHOR_RULES"]

ANCHOR_RULES = """The citation is an ADDRESS as well as a quotation: it is the text the reader \
will copy as the `find` of their edit. Cite the SMALLEST span that is unique in \
the file — a few lines, never a whole function body — sitting exactly where the \
change meets it. Three modes:

  APPLY insert_after    the new code goes AFTER the cited lines
  APPLY insert_before   the new code goes BEFORE them
  APPLY replace_span    the cited lines are REPLACED by the new code

Pick the one that makes the anchor SMALL and adjacent. A guard goes BEFORE the \
statement it guards, so cite that statement and say `insert_before` — citing \
the whole function and saying `insert_after` puts the guard after the thing it \
was meant to prevent, which is a bug that reads as correct.

On an `insert_after`, the anchor's LAST LINE decides where the code lands, and \
BOTH ways of getting it wrong were measured:

  * Never end the anchor on a line that OPENS a block the change does not \
belong in. An anchor ending on `except OSError as e:` put a guard INSIDE the \
except clause it was supposed to run before — the prose was right and the \
address was not.
  * Never end it on the `end`/`}`/`)` that CLOSES the block the change belongs \
in — that puts the change outside the class, describe or function.

So when the new code is a SIBLING that goes after an existing block — another \
test in a suite, another method in a class — the anchor must include that \
block's own closing line, and NOTHING after it. Cite the last lines of the \
sibling plus its `end`. An anchor that stops before the `end` nests the new \
block inside the old one; measured, this is the single thing that cost a reader \
an extra file read.

Put a test where the tests of the function you are mirroring ALREADY live. If \
the answer carries a "tests that pin this behaviour" section, that file is the \
answer — it was computed from the index, not guessed — and proposing a \
different one contradicts your own evidence."""
