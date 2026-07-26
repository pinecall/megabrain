"""The instruction to go and LOOK, and why it sits at the very top.

MEASURED, twice, and the second measurement is the one that mattered. As a
clause among the citation rules at the end of a prompt carrying thirty chunks of
code, it was obeyed ZERO times out of four questions — including one that said
"open this file" in so many words. Moved to the top and paired with a bounded
body budget (`MAX_BODIES`), the same narrator opened exactly the two files an
end-to-end trace was missing, and opened nothing on the two questions whose code
was already quoted.

Position was necessary and not sufficient: what a model does with enough
material to write something is write it. The instruction only becomes real when
the prompt stops answering the question for it.
"""

from __future__ import annotations

__all__ = ["OPENING"]

OPENING = """\
FIRST, BEFORE WRITING ANYTHING: the chunks below were chosen by similarity, so
they are where the answer starts and rarely all of it — and the ones listed
without code are yours to open. Read the query, list to yourself every step the
answer must cover, and for each step not fully present below call `open_file`.
Open them ALL IN ONE TURN. You must do this whenever:

  * a chunk CALLS something whose definition is not below — the walkthrough has
    to say what that call does, and a name is not behaviour
  * the query asks for a chain, a trace or an end-to-end flow: one missing link
    makes the whole answer a guess
  * the query names a file, function or test you cannot see in full

Opening costs one round trip. Answering "that is not in the retrieved context"
about code this repository contains is the one failure this tool exists to
prevent — the caller cannot see the chunks, and asked YOU to go and look.\
"""
