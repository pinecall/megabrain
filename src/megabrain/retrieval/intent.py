"""What the question is asking for — read from the question, deterministically.

One signal so far, and it earned its own module the hard way. `test_penalty`
exists because tests quote the implementation's vocabulary by design; applied
blind, it took the best-matching chunk in a repository — the four canonical
`halt` tests, rank #0 of 2 700 by raw cosine — and delivered it at #115 for the
query "where are the tests for halt?".

No model. This runs on the query path of every search, where a network round
trip in front of a 4 ms answer is not a trade anyone would take, and where a
non-deterministic verdict would make the same question rank differently between
runs.
"""

from __future__ import annotations

import re

__all__ = ["wants_tests"]

# The noun, not the verb: "tests", "spec", "test coverage". `tested` is here
# because "where is this behaviour tested" is the same request phrased as a
# participle, and that phrasing is common enough to matter.
_ASKS = re.compile(
    r"\b(tests?|testing|tested|specs?|test[- ]?(?:case|suite|coverage|file)s?)\b",
    re.IGNORECASE)

# The trap this rule exists to survive: a question ABOUT the machinery that
# runs tests is a question about implementation, and it mentions tests more
# than any other kind of query. "how does the test runner discover test files"
# must NOT down-rank the runner in favour of the tests it discovers.
_ABOUT_THE_MACHINERY = re.compile(
    r"\btest[- ]?(?:runner|harness|framework|fixture|helper|loader|driver)s?\b"
    r"|\b(?:runs?|running|discover(?:s|ing)?|load(?:s|ing)?|collect(?:s|ing)?)"
    r"\s+(?:the\s+)?tests?\b",
    re.IGNORECASE)


def wants_tests(query: str) -> bool:
    """Whether the question is asking FOR tests rather than about the code.

    Deliberately narrow. A false positive costs the down-weight that keeps
    tests from crowding an implementation answer, so the rule only fires on a
    question that names tests as the THING WANTED — and it stands down entirely
    when the question is about the machinery that runs them.
    """
    if _ABOUT_THE_MACHINERY.search(query):
        return False
    return bool(_ASKS.search(query))
