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

from .wording import ASKING_WORDS, CHANGING_STEMS, TEST_NOUNS, WANTING_PHRASES

__all__ = ["wants_tests", "is_task"]

# What the sentence is FOR. An interrogative opening decides it outright:
# "how do I add a cache header" says "add" and is still a question, and that
# phrasing is the one most likely to fool a verb list. The non-English openers
# come from `wording.py` — data, so a language is a row, not a redesign.
_ASKING = re.compile(r"^\s*(how|where|what|why|which|who|when|does|do|is|are|"
                     r"can|should|explain|describe|show|"
                     + "|".join(ASKING_WORDS) + r")\b", re.IGNORECASE)

# The verbs that name a CHANGE to the repository. Anchored to the start of a
# clause so "where does the indexer add chunks" — a description of code that
# adds — is not read as a request to add anything. English keeps its measured
# exact list; the other languages match as stems (`\w*` covers conjugation).
_CHANGING = re.compile(
    r"(^|[.;]\s*|\b(?:and|y|e|et|und)\s+)"
    r"(add|implement|create|build|write|introduce|support|"
    r"fix|change|update|modify|rename|remove|delete|drop|refactor|migrate|"
    r"wire|hook|extend|replace|make|"
    + "|".join(stem + r"\w*" for stem in CHANGING_STEMS) + r")\b",
    re.IGNORECASE)

# The other way people phrase a change: "we need a way to…", "it should…".
_WANTING = re.compile(r"\b(we|i)\s+(need|want)\b|\bshould\s+be\s+able\b|\b(?:"
                      + "|".join(WANTING_PHRASES) + r")\b", re.IGNORECASE)

# The noun, not the verb: "tests", "spec", "test coverage". `tested` is here
# because "where is this behaviour tested" is the same request phrased as a
# participle, and that phrasing is common enough to matter.
_ASKS = re.compile(
    r"\b(tests?|testing|tested|specs?|test[- ]?(?:case|suite|coverage|file)s?|"
    + "|".join(TEST_NOUNS) + r")\b",
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


def is_task(query: str) -> bool:
    """Whether this asks for a CHANGE rather than an explanation.

    The two want opposite deliverables. A question wants the flow narrated; a
    task wants the edit surface — the files that must change, opened, with the
    place the change goes. Measured: answering a task as a question cost a
    second round trip, because the first answer said HOW it works and the agent
    still had to ask WHERE to type.
    """
    if _ASKING.match(query):
        return False
    return bool(_CHANGING.search(query) or _WANTING.search(query))


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
