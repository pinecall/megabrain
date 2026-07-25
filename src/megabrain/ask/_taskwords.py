"""The wording of the task prompt — its own module because it IS the behaviour.

Every clause was written against something that went wrong: the APPLY marker
because prose left the agent rebuilding operations by hand; DO NOT WRITE THE
CODE because an authored guard ran after the write it guarded; the three modes
because a guard needs to go BEFORE its statement and only "after" existed.
"""

from __future__ import annotations

__all__ = ["PROMPT"]

PROMPT = """An engineer is about to make this change to the codebase:

{task}

Retrieval found these files. This is a MAP — paths and the symbols each file \
declares, no code:

{map}

Your job is to hand back the EDIT SURFACE: every file this change must touch, \
ready to edit. Work in two steps.

STEP 1 — open what you need, ALL AT ONCE, in a SINGLE turn: the file to \
change, the test file covering it, and the nearest example to imitate. One \
file per turn is a network round trip per file. Always include the test — a \
change without its test is half an edit surface.

STEP 2 — write the surface. For EACH file that must change, in the order it \
should be edited, EXACTLY this shape:

## <path> — <what changes here>, at line <N>
[[<path>:<from>-<to>]]
APPLY insert_after
<Two or three sentences SPECIFYING the change, for the engineer who will type \
it: what it must do, which existing helper it must call by name instead of \
re-deriving, which error or return shape it must match, and the edge case that \
would be easy to miss. Be precise about behaviour and silent about syntax.>

DO NOT WRITE THE CODE. You produce a specification and an address, not a patch \
— the reader writes the code and runs the tests, and those two belong together. \
Naming the wrong helper is a sentence they catch on the way past; a \
plausible-looking block they paste is a bug they do not.

{anchor_rules}

NAME the edge case. The one that cost the most: a guard added to a function \
that CREATES files must not reject a path that does not exist yet. Say it in a \
sentence — that sentence is worth more than any code you could write here.

Then a section "## Pattern to follow", citing complete siblings — each one \
spanning from its own first line to its own end, never the class, describe or \
module that contains it. A container is the whole suite and costs more than \
opening the file would.

CITE EVERY HELPER YOU TELL THEM TO REUSE. Naming one is not enough — the \
reader needs its signature, its defaults and what it does to the response \
before they can call it correctly. Measured: told to reuse `content_type`, \
`attachment` and `halt`, an agent had to ask a second question to learn that \
the body setter DELETES content-length, without which it would have set that \
header by hand and been silently wrong.

When the change MIRRORS something the codebase already does — the same guard on \
a sibling function, the same option on a sibling class — cite that original in \
full, every occurrence of it. It is the specification: its exact wording, its \
comment, its error string are what "the same as" means, and the reader will go \
and open the file to get them if you only describe them.

For a TEST, cite TWO OR THREE siblings, chosen to show the file's IDIOMS rather \
than its subject: how it skips a platform, how it builds its fixture, how it \
asserts. One example shows the shape; three show the conventions.

Never cite the same range twice anywhere in your answer.

Rules:
- Code appears ONLY as a [[path:from-to]] citation, which the engine replaces \
with the verbatim source. You never type a line of code — not existing code, \
which retyping silently changes, and not new code, which you cannot test.
- A citation whose range you have not opened is a guess. Open it.
- Only cite paths that exist in this repository.
- No preamble, no summary of the codebase. The reader is about to edit.

Exactly this shape, and nothing else:

## lib/foo.rb — add `bar`, after `baz` at line 42
[[lib/foo.rb:38-42]]
APPLY insert_after
Add a `bar(arg)` beside `baz`, taking the same argument and returning what \
`baz` returns, falling back to `fallback` when it returns nil. Call `baz` — do \
not repeat what it does. It must return, never raise, when `arg` is empty: \
`baz` already treats that as the fallback case.

## Pattern to follow
[[lib/foo.rb:38-42]]

Note what that example never does: write code."""
