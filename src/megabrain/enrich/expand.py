"""The expander: naming the vocabulary a query did not have.

The judge can only reorder what cosine FOUND. When the answer never enters the
pool, no reordering rescues it — measured on sinatra, where the four canonical
`halt` tests were invisible to their own query's wording and two agents fell
back to grep.

So one cheap call NAMES IDENTIFIERS — the method, class or constant the code
itself uses and the question did not say — and the SYMBOL TABLE resolves them
to the files that define them. The model never picks a file and never picks a
span: a bad name resolves to nothing, which costs a round and never a wrong
answer. And it only ever ADDS, the same contract the recall floors keep, which
is what makes an extra lane strictly better than no lane rather than a gamble.

Naming and resolving are split on purpose: `retrieval/bundle/widen.py` holds
the measurement that chose the symbol table over the embedder. This module owns
the conversation, not what an identifier means.

It LOOPS. One round names what the query lacked; the next names what that round
revealed. It stops when a round adds nothing, because how deep an answer sits is
a property of the repository, not a number the caller can guess.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Protocol

from ..contracts import Bundle, Tier2File
from ._echo import useful_terms
from ._terms import MAX_TOKENS, prompt_for

__all__ = ["expand", "MAX_ROUNDS"]

MAX_ROUNDS = 3
"""A backstop, not the expected depth: the loop normally stops itself when a
round adds nothing. This is what keeps a namer that keeps finding new things
from spinning while the caller waits on a model call per round."""


class Namer(Protocol):
    def chat_text(self, model: str, prompt: str, max_tokens: int = 1024,
                  temperature: float = 0.0) -> str: ...


Resolve = Callable[[list[str], set[str]], list[Tier2File]]
"""(identifiers, files already held) -> the RELATED entries they define. The
held set travels along so the resolver can skip building what would be
discarded."""


def expand(bundle: Bundle, namer: Namer, resolve: Resolve) -> Bundle:
    """Widen `bundle` with the files its named identifiers define.

    Fails open: no provider, a timeout, a malformed reply or a name that
    resolves to nothing all return the deterministic bundle untouched.
    """
    query = bundle["query"]
    core = list(bundle["tier1"])
    widened = list(bundle["tier2"])
    named: list[str] = []
    for _round in range(MAX_ROUNDS):
        tried = {term.lower() for term in named}
        # CORE included on purpose: the lane judges what is MISSING, and a
        # listing that hides the files the bundle was most confident about
        # invites a name pointing at something already found.
        terms = [t for t in _ask(namer, query, core + widened)
                 if t.lower() not in tried]
        if not terms:
            break                  # nothing said, or nothing this round HASN'T said
        held = {e["file"] for e in core} | {e["file"] for e in widened}
        named += terms
        fresh = _resolved(resolve, terms, held)
        if not fresh:
            break                  # a round that adds nothing is the stop signal
        widened += fresh
    if not named:
        return bundle
    return {**bundle, "tier2": widened, "expanded": named}


def _ask(namer: Namer, query: str, found: list[Any]) -> list[str]:
    """The terms this round proposes, or [] on any failure at all."""
    try:
        reply = namer.chat_text(getattr(namer, "model", ""),
                                prompt_for(query, found), max_tokens=MAX_TOKENS)
        array = re.search(r"\[.*?\]", reply, re.DOTALL)
        raw = [str(term).strip() for term in json.loads(array.group(0))] if array else []
    except Exception:              # noqa: BLE001 — an optimisation, never a dependency
        return []
    return useful_terms(query, raw)


def _resolved(resolve: Resolve, terms: list[str], held: set[str]) -> list[Tier2File]:
    """What the names point at, or [] — same fail-open contract as the naming."""
    try:
        return [entry for entry in resolve(terms, held) if entry["file"] not in held]
    except Exception:              # noqa: BLE001 — an optimisation, never a dependency
        return []
