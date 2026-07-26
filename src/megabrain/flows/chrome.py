"""Stripping the citation chrome before a cached flow goes back to a model.

A stored flow is the RENDERED answer, so it carries the formatting the splice
wrote around every block: a header like **`src/x/y.py` L58-83** above each
fenced chunk.

Shown that format as context, the model IMITATES it. It emits headers instead
of `[[k]]` citations, so the splicer has nothing to replace — and the answer
names files, lines and symbols while displaying NO CODE AT ALL. Reported live:
a question that matched two cached flows rendered eight such headers and not
one line of code.

That failure is invisible from the model's side. It looks like a well-formatted
answer. So the chrome comes off before the text is ever shown to one.
"""

from __future__ import annotations

import re

from ..ask.citing.splice import BLOCK_HEADER

__all__ = ["strip_chrome"]

_CITATION = re.compile(r"\[\[[^\]]*\]\]")
_FENCED = re.compile(r"```.*?```", re.DOTALL)
_BLANK_RUN = re.compile(r"\n{3,}")


def strip_chrome(answer: str) -> str:
    """The PROSE of a rendered walkthrough: no code blocks, no block headers,
    no leftover citations.

    The code goes too, and that is not a loss: the narrator gets the real code
    from retrieval every time. What a cached flow adds is the EXPLANATION —
    which files matter, in what order, and why — and pasting stale code beside
    fresh code is how a reader ends up comparing two versions of a function
    without being told which is which.
    """
    text = _FENCED.sub("", answer)
    text = BLOCK_HEADER.sub("", text)
    text = _CITATION.sub("", text)
    return _BLANK_RUN.sub("\n\n", text).strip()
