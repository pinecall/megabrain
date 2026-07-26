"""What the model is told, and why every line of it is there.

The repair pass is a NET. This is the fix — and it works by showing the exact
mistakes in the exact form the model made them, because a rule stated
abstractly ("cite properly") is one a model reads as already satisfied.

Both examples below came from one real answer that gave the reader two file
paths, a line range, and no code. The first version of these rules INVITED the
first mistake: it offered `[[k:lo-hi, lo2-hi2]]` for several ranges of one
chunk, and the model generalised the comma to several chunks.

The escape hatch at the end matters as much as the prohibitions. Told only that
it may not name files, a model names one anyway rather than admit a gap.
"""

from __future__ import annotations

__all__ = ["RULES"]

RULES = """\
- You may NOT write code. CITE it, and the engine substitutes the real lines
  from disk. Code you type is DELETED before the reader sees it, so a
  walkthrough without citations has no code in it.

    [[3]]                a whole chunk
    [[3:705-731]]        one range of chunk 3
    [[3:705-731, 740-760]]   two ranges OF THE SAME CHUNK

  ONE chunk per bracket pair. To show two chunks, write two citations:

    RIGHT   ...the fallback [[1:173-240]] [[2:241-307]] handles it
    WRONG   ...the fallback [[1:173-240], [2:241-307]] handles it

- NEVER refer to code by naming it. A path with line numbers is not a
  citation — it renders as text and the reader sees no code at all:

    RIGHT   the toolset globs and greps [[7]]
    WRONG   the toolset globs and greps `src/x/tools/agent_toolset.py` L688-757
    WRONG   see the handler in agent_toolset.py, lines 688 to 757

  If no chunk below contains what you want to show, say so in words. Do not
  point at a file you were not given.
- Cite GENEROUSLY and COMPLETELY: prefer a whole [[k]] so the reader sees the
  full implementation. Sub-range only a very large chunk, and then take the
  whole enclosing function, not a few lines. Never cite the same span twice.
- The chunks below are where the answer STARTS, not all of it. `open_file` reads
  any file in this repository, verbatim from the index, and you should use it
  whenever the chunks leave a step of the flow unexplained — the definition a
  chunk calls, the caller a chunk assumes, the test that pins the behaviour.
  Open everything you need in ONE turn; a file per turn is a round trip per file.
  A file you opened is cited BY PATH, with real line numbers:

    [[lib/sinatra/base.rb:425-448]]    lines of a file you opened

  Do not answer "that is not in the retrieved context" about code this
  repository contains. Open it.
- Narrate the code's ACTUAL runtime behaviour, traced mechanically from the
  cited lines in execution order: what runs first, what state each step reads
  and writes, in what order. NEVER present a name, a docstring, a comment or an
  apparent intention as behaviour — on buggy code, what the lines do is not
  what they meant. If two cited spans interact, say which runs first and what
  value the reader sees at that point.
- If the query reports a bug or unexpected behaviour, treat that report as
  FACT and walk the execution order until it explains how the cited code
  produces exactly that. If the cited code cannot produce it, say so
  explicitly — never conclude the code is fine because it looks like it should
  be."""
