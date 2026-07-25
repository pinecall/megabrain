"""How big a request may be, and the estimate that decides.

Its own module because it is a MEASUREMENT policy, not connection config: the
endpoint's URL and key say where to send a batch, this says how much may go in
one.
"""

from __future__ import annotations

__all__ = ["MAX_BATCH_TOKENS", "CHARS_PER_TOKEN", "estimate_tokens"]

MAX_BATCH_TOKENS = 100_000
"""The size ceiling a batch must not cross, in ESTIMATED tokens.

A count of texts is not a measure of a request. Ninety-six small texts is a fine
batch and ninety-six large ones is an impossible one — measured in the wild, a
repository of generated files sent 164 614 tokens against a 120 000 limit and
the whole index failed on it.

Under the real limit on purpose: the estimate below is characters over four,
which is close for prose and code and wrong for anything dense. The headroom is
what keeps "close" from meaning "refused".
"""

CHARS_PER_TOKEN = 2.0
"""Characters per token, and the number is CONSERVATIVE on purpose.

MEASURED, twice, on the requests that failed. A batch of 96 real source files —
305 503 characters — came back as **120 436 tokens**: 2.54 chars per token, not
the 4 that prose suggests. Code is punctuation, and punctuation is tokens.

2.0 rather than 2.54 because 2.54 was measured on ONE repository's Python. A
minified bundle or a wall of JSON is denser still, and the estimate has to hold
for the worst file in the repository, not the average one. At 2.0 the budget
below stays under a 120 000-token limit for anything down to 1.67 chars/token —
which no human-written source reaches.

The cost of being wrong in this direction is one extra round trip. The cost of
being wrong in the other direction is the whole index failing, which is what
happened.
"""


def estimate_tokens(text: str) -> int:
    """Deliberately not a tokeniser: loading one costs a dependency, a model
    file and startup time to answer a question that only has to be
    approximately right — with the headroom above covering the rest."""
    return int(len(text) / CHARS_PER_TOKEN) + 1
