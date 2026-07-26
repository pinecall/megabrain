"""Which words in a task are identifiers worth chasing, and which rows survive.

Both halves keep the literal-mention lane from drowning in its own recall, and
both are measured. Without the identifier filter a task's ordinary English —
`value`, `option`, `help` — matches the whole repository. Without the containment
filter a closure inside a test is listed beside the test that holds it, pointing
twice at one edit.
"""

from __future__ import annotations

import re

__all__ = ["identifiers", "outermost", "MIN_IDENT"]

MIN_IDENT = 8
"""Characters a name needs to be chased on SHAPE alone, with no index consulted.

Eight keeps the distinctive names — `show_envvar`, `resolve_envvar_value`,
`audio_processor` — which are the ones a task shares with its edit sites."""

MIN_DECLARED = 4
"""Characters a name needs when the INDEX vouches for it.

Shorter, because the guess is gone: `json` is four characters and matters, while
`with` is four and no repository declares it."""

MAX_COMMON = 12
"""Definitions a declared name may have before it is the repository's vocabulary.

`render` in five files is this task's target; a `run` every class defines is not,
and admitting one costs the whole lane — forty resolved sites trip `MAX_SPREAD`
and return NOTHING, holding the row that mattered."""

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_SNAKE_OR_CAMEL = re.compile(r"_|[a-z][A-Z]")


def identifiers(task: str, known: dict[str, int] | None = None) -> set[str]:
    """The distinctive names in the task: shaped like code, or declared as code.

    `_SNAKE_OR_CAMEL` separates `show_envvar` from `environment`: prose contains
    long English words too, and chasing those returns files that merely discuss
    the subject. That guess is all there is when `known` is absent — which is the
    case for a code BODY, where every declared name it touches would match.

    Given `known` (bare name -> definition count) the guess stops being needed
    for the words the repository itself declares, and MEASURED, the guess was
    WRONG in a way that tracked language. "add res.inline beside res.attachment"
    yielded only `contentDisposition`: `attachment` is ten characters of one
    lowercase word, so shape rejected the task's most important name, while the
    index has it at `lib/response.js:606`. Single-word names are the norm in
    JS and Ruby (`attachment`, `render`, `download`) and the exception in
    snake_case Python — so a shape rule is a bias toward Python dressed up as a
    heuristic. The index is not a heuristic: it knows `attachment` and has never
    heard of `beside`.
    """
    words = _IDENT.findall(task)
    shaped = {word for word in words
              if len(word) >= MIN_IDENT and _SNAKE_OR_CAMEL.search(word)}
    if known is None:
        return shaped
    return shaped | {word for word in words if len(word) >= MIN_DECLARED
                     and 0 < known.get(word, 0) <= MAX_COMMON}


def outermost(symbols: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """Symbols not contained inside another that is already listed.

    A closure inside a test — `test_show_envvar.cmd` at L759-762 inside
    `test_show_envvar` at L758-766 — is not a second place to go. Listing both
    doubles the rows and points twice at one edit.
    """
    return [(name, low, high) for name, low, high in symbols
            if not any(other_low <= low and high <= other_high
                       and (low, high) != (other_low, other_high)
                       for _, other_low, other_high in symbols)]
