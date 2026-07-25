"""Which proposed identifiers are worth resolving.

Split from the asking (`_terms.py`) because it is a different job: that module
decides what the model is TOLD, this one decides what it is BELIEVED about.

The echo is the expensive failure and the reason this is code rather than a
line in the prompt. A model that answers "halt, tests" to "where are the tests
for halt" has said nothing, but it reads as progress — terms came back, a
lookup ran, files arrived — while re-resolving what the question already
contained. An instruction the model can ignore is not a guarantee, and this one
costs nothing to enforce.
"""

from __future__ import annotations

import re

__all__ = ["useful_terms", "MAX_TERMS"]

MAX_TERMS = 4
"""Identifiers admitted per round. Each one is a symbol lookup and up to three
files, so this is the width of one round's widening — enough for a mechanism's
vocabulary, short of burying the tier it adds to."""


def useful_terms(query: str, proposed: list[str]) -> list[str]:
    """The proposed names minus the ones that cannot teach the search anything.

    Dropped: blanks, duplicates, anything that looks like a path (the model
    guessing at filenames it cannot know), and ECHOES — a term whose every word
    the query already contains.
    """
    known = _words(query)
    kept: list[str] = []
    for term in proposed:
        term = term.strip().strip("`'\"")
        if not term or "/" in term or "." in term:
            continue
        if term.lower() in {t.lower() for t in kept} or _words(term) <= known:
            continue
        kept.append(term)
    return kept[:MAX_TERMS]


def _words(text: str) -> set[str]:
    """Lowercased word-parts, splitting camelCase and snake_case alike, so that
    `haltRequest` counts as an echo of a query that said "halt request"."""
    parts = re.split(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])", text)
    return {part.lower() for part in parts if part}
