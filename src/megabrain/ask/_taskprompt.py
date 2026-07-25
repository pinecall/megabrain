"""What the narrator is asked when the request is a CHANGE.

A question and a task want opposite deliverables from the same retrieval. The
walkthrough prompt answers "how does this work"; a task needs "where do I
type". Measured, asking a task the question-shaped way cost a whole extra round
trip: the narrator explained the mechanism, and the agent came back with
"donde esta definido el helper redirect".

Two rules carry the weight:

  * OPEN before proposing. The map names files; only the file itself shows the
    region an edit lands in and the style of its neighbours.
  * CITE, never retype. The model names a path and a line range; megabrain
    splices those lines verbatim out of the index. A model that types the code
    back is a model that can quietly change it.
"""

from __future__ import annotations

from ..contracts import Bundle

__all__ = ["build_task_prompt", "MAX_MAP_FILES"]

MAX_MAP_FILES = 20

PROMPT = """An engineer is about to make this change to the codebase:

{task}

Retrieval found these files. This is a MAP — paths and the symbols each file \
declares, no code:

{map}

Your job is to hand back the EDIT SURFACE: every file this change must touch, \
ready to edit. Work in two steps.

STEP 1 — open what you need. Call `open_file` for each file the change will \
touch, and for the file holding the nearest existing example to imitate. \
Always open the test file that covers the code you are changing: a change \
without its test is half an edit surface. Open before you conclude — the map \
tells you a file exists, not what its code looks like.

STEP 2 — write the surface. For EACH file that must change, in the order it \
should be edited:

## <path> — <what changes here>, at line <N>
CITE the surrounding code with a citation of the form [[<path>:<from>-<to>]] \
on its own line. Say what to insert or replace, and why that line: name the \
symbol above and below it. If an existing helper should be reused instead of \
new logic, name it and cite where it is defined.

Then one short section "## Pattern to follow" citing the nearest existing \
example — the neighbouring test, or the sibling helper — so the new code \
matches what is already there.

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
Insert after line 42. `baz` above it does X; reuse it rather than repeating \
its logic. The new lines:
```ruby
def bar(arg)
  baz(arg) || fallback
end
```

Note what that example does NOT do: it never repeats the lines it just cited \
inside the new block. The citation shows what is there; the block shows only \
what to type."""


def build_task_prompt(task: str, bundle: Bundle) -> str:
    """The map plus the instructions. Bodies are deliberately absent — the
    model pulls what it needs with `open_file`, which is what keeps a task
    about three files from carrying twenty files of code it will not touch."""
    lines: list[str] = []
    for entry in _files(bundle)[:MAX_MAP_FILES]:
        names = [str(s.get("name", "")) for s in (entry.get("symbols") or [])][:8]
        shown = ", ".join(n for n in names if n)
        lines.append(f"- {entry['file']}" + (f"  ({shown})" if shown else ""))
    return PROMPT.format(task=task, map="\n".join(lines) or "- (nothing found)")


def _files(bundle: Bundle) -> list[dict]:
    """CORE first, then RELATED — the ranking's own order, unaltered."""
    return [*bundle["tier1"], *bundle["tier2"]]      # type: ignore[list-item]
