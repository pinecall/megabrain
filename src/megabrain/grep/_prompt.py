"""What the model is asked for when the caller is about to EDIT.

Its own module because it IS the behaviour, the same reason the walkthrough rules
live apart from the code that sends them.

Every clause is a lesson this engine paid for. The retired `megabrain_code`
quoted anchors, specs and helper bodies — and the host's editor made the reader
open those files anyway, so the citation was work billed twice. What survived
that measurement is the part no grep can do: knowing WHICH symbol in which file
matters, and why this one and not its neighbour.
"""

from __future__ import annotations

__all__ = ["GREP_PROMPT"]

GREP_PROMPT = """An engineer is about to make this change, and needs to know \
where to look:

{task}

Retrieval found these files — paths and the symbols each declares, no code:

{map}

`open_file` reads any file here. Open what you need to be SURE, all in one turn.

Then answer with ONE LINE PER SYMBOL worth opening, and nothing else:

path/to/file.ext | symbol_name | why this one, under 100 characters

Rules that make this useful instead of a second walkthrough:

- ONE row per symbol. No prose before the rows, no summary after them, no \
blank-line paragraphs explaining your reasoning — the caller is about to open \
these files and every extra line is a line between them and the edit.
- Do NOT quote code. Not a line of it. The caller's editor opens the file; \
pasting it here means they read it twice.
- Do NOT write line numbers. Name the symbol and the engine numbers it from the \
index, exactly, which is a thing you cannot do by counting.
- `symbol_name` must be a real declared name — a method, function, class or \
test. `send_file`, `Session.create`, `test_rejects_directory`. Not a file, not a \
concept, not a line of prose.
- Order the rows the way the work happens: the site to CHANGE first, then what \
it must match or reuse, then the test that pins it.
- Include the TEST that covers this, always. A change without its test is half \
a job, and the test file's own name is not enough to find it.
- Include the ORIGIN of every value the change carries. The origin is where \
the value is ASSIGNED or computed (`self.x =`, the method that translates an \
option into it) — not where it is read, not the flow that consumes it. Find \
the actual assignment: search the bodies you were given, and if none contains \
it, OPEN files until you see the `=`. That file usually shares no words with \
the task, which is exactly why it needs a row — no search ranks it, and a fix \
written from the use sites alone duplicates logic that already exists one \
file away. Note it like: "assigns X from Y — the one place that knows the \
shape".
- The note says why THIS symbol: "the guard to copy", "no guard, add it here", \
"pins the old behaviour". Not what the code is — the caller is about to read it.

If nothing in this repository is relevant, say so in one sentence and give no \
rows. An invented row costs the caller a file open and their trust."""
