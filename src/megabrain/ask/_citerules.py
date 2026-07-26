"""What to SHOW alongside an address — the third half of the prompt.

Separate from the anchor rules because it answers a different question. Those
say where the change goes; these say what the reader needs in front of them to
write it, and every clause is a read someone actually made:

  * the original a change mirrors — an agent opened a file for "the literal
    error string and comment style" of the guard it was copying
  * two or three test siblings, for the idioms — one went hunting with grep for
    how a file spells a platform skip

The helpers a spec names are NOT asked for here anymore: `_callees.py` cites
their definitions mechanically, because asked-for citing was skipped three
times out of four measured tasks.
"""

from __future__ import annotations

__all__ = ["CITE_RULES"]

CITE_RULES = """Then a section "## Pattern to follow", citing complete siblings — each one \
spanning from its own first line to its own end, never the class, describe or \
module that contains it. A container is the whole suite and costs more than \
opening the file would.

NAME every helper the reader must reuse in backticks — `content_type`, \
`resolve_path` — and the engine cites its definition for you, verbatim from \
the index. Do not describe from memory what a helper returns or side-effects; \
the cited definition is the authority, and a description that disagrees with \
it is exactly the sentence that gets pasted.

When the change MIRRORS something the codebase already does — the same guard on \
a sibling function, the same option on a sibling class — cite that original in \
full, every occurrence of it. It is the specification: its exact wording, its \
comment, its error string are what "the same as" means, and the reader will go \
and open the file to get them if you only describe them.

For a TEST, cite TWO OR THREE siblings, chosen to show the file's IDIOMS rather \
than its subject: how it skips a platform, how it builds its fixture, how it \
asserts. One example shows the shape; three show the conventions."""
