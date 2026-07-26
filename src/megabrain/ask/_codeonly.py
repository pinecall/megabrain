"""Matching a symbol in CODE, not in the sentence that describes something else.

MEASURED. Asked to make sinatra's `back` reject a cross-host referer, two
unrelated suites outranked the one that mattered: `it 'falls back to engine
layout'` and `it 'falls back on the next server handler'`. The English phrase
"falls back" contains the symbol, so tests that merely DESCRIBE other things
pushed the test that actually calls it into third place — and on a longer answer
that ordering gets the real warning skimmed past.

The genuine one has `redirect back` in its body. A symbol inside a sentence is a
coincidence; a symbol in code is a use.
"""

from __future__ import annotations

import re

__all__ = ["outside_strings"]

_STRINGS = re.compile(r"""'[^'\n]*'|"[^"\n]*\"""")
"""Single-line literals in either quote style.

Deliberately not a lexer: it runs over every chunk of a repository, and the
cost of a mistake is one ranking place. Line-bounded so an unbalanced quote in a
comment cannot swallow the rest of a file."""


def outside_strings(text: str) -> str:
    """`text` with string literals blanked out, leaving the code around them."""
    return _STRINGS.sub("", text)
