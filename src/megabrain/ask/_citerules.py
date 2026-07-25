"""What to SHOW alongside an address — the third half of the prompt.

Separate from the anchor rules because it answers a different question. Those
say where the change goes; these say what the reader needs in front of them to
write it, and every clause is a read someone actually made:

  * the original a change mirrors — an agent opened a file for "the literal
    error string and comment style" of the guard it was copying
  * every helper the spec says to reuse — one asked a second question to learn
    that the body setter deletes content-length
  * two or three test siblings, for the idioms — one went hunting with grep for
    how a file spells a platform skip
"""

from __future__ import annotations

__all__ = ["CITE_RULES"]

CITE_RULES = """Then a section "## Pattern to follow", citing complete siblings — each one \
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
asserts. One example shows the shape; three show the conventions."""
