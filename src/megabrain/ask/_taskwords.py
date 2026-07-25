"""The wording of the task prompt — its own module because it IS the behaviour.

Every clause here was written against something that went wrong. The APPLY
marker exists because a surface handed over as prose left the agent rebuilding
exact-string operations by hand, one file at a time. The indentation rule
exists because a block spliced in one level too deep ships one level too deep.
The worked example exists because, told in rules alone not to retype the code
it had just cited, the model retyped it anyway — with different indentation.
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

STEP 1 — open what you need, ALL AT ONCE. Issue every `open_file` call you \
need in a SINGLE turn: the implementation file, the test file that covers it, \
and the file holding the nearest example to imitate. One file per turn costs a \
network round trip each and is the slowest thing you can do here. Always \
include the test file — a change without its test is half an edit surface. \
Open before you conclude: the map says a file exists, not what its code says.

STEP 2 — write the surface. For EACH file that must change, in the order it \
should be edited, EXACTLY this shape:

## <path> — <what changes here>, at line <N>
[[<path>:<from>-<to>]]
APPLY insert_after
```<lang>
<only the new lines>
```
<one or two sentences: why that line — name the symbol above and below it, and \
name any existing helper the new code should reuse instead of repeating.>

The citation is an ANCHOR as well as a quotation: the engine reads those exact \
lines out of the index and builds the edit from them, so cite a span that is \
UNIQUE in the file (a few lines, not one common closing `end`) and that sits \
immediately before where the new code goes. Use `APPLY replace_span` instead \
when the cited lines should be REPLACED by yours rather than kept.

The anchor's LAST LINE is the insertion point: your code is placed immediately \
after it, inside whatever block that line is inside. So never end an anchor on \
a line that CLOSES the block your code belongs in — an anchor ending on the \
`end`/`}`/`)` that closes a class, describe or function puts your code outside \
it. End the anchor on the last line of the SIBLING your code goes next to.

INDENT the new lines to exactly the indentation of that sibling — your block is \
spliced in directly, so one level too deep ships as one level too deep. If the \
sibling starts with four spaces, so does your first line.

REUSE what the task told you to reuse. If an existing helper does part of the \
job, call it by name; re-deriving what it already returns is the change being \
done wrong, however well it reads.

Then ONE section "## Pattern to follow" with exactly ONE citation: the single \
nearest existing example — one test, or one method — spanning it COMPLETELY, \
from its own first line to its own `end`. Not the class, describe or module \
that contains it: a container is the whole suite, and quoting it costs more \
than the reader was going to spend opening the file. One complete sibling is \
what they cannot reconstruct from anywhere else. Never cite the same range \
twice anywhere in your answer.

Rules:
- EXISTING code is never retyped. Every line that is already in the repository \
must appear as a [[path:from-to]] citation, which megabrain replaces with the \
verbatim source. Retyping it is how a line silently changes.
- NEW code you propose goes in a plain fenced block containing ONLY the lines \
to add — never the surrounding lines you just cited.
- A citation whose range you have not opened is a guess. Open it.
- Only cite paths that exist in this repository.
- No preamble, no summary of the codebase. The reader is about to edit.

Exactly this shape, and nothing else:

## lib/foo.rb — add `bar`, after `baz` at line 42
[[lib/foo.rb:38-42]]
APPLY insert_after
```ruby
def bar(arg)
  baz(arg) || fallback
end
```
`baz` at line 38 already resolves the argument; reuse it rather than repeating \
its logic.

Note what that example does NOT do: the fenced block never repeats the lines \
it just cited. The citation is what is already there; the block is only what \
to type."""
