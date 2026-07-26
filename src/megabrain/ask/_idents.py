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
"""Characters an identifier needs before it is worth chasing repo-wide.

Eight keeps the distinctive names — `show_envvar`, `resolve_envvar_value`,
`audio_processor` — which are the ones a task shares with its edit sites."""

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_SNAKE_OR_CAMEL = re.compile(r"_|[a-z][A-Z]")


def identifiers(task: str) -> set[str]:
    """The distinctive names in the task: long, and shaped like code.

    `_SNAKE_OR_CAMEL` is what separates `show_envvar` from `environment`: a
    task's prose contains long English words too, and chasing those returns
    files that merely discuss the subject.
    """
    return {word for word in _IDENT.findall(task)
            if len(word) >= MIN_IDENT and _SNAKE_OR_CAMEL.search(word)}


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
