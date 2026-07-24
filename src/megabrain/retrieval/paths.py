"""Reading meaning out of a file path.

Vocabulary, not tuning: these sets say what a path IS. The weights applied to
them live in `params`, so a policy change is a number and a taxonomy change is
a word.
"""

from __future__ import annotations

import re

__all__ = ["is_test", "is_demo", "under", "ident_tokens", "TEST_SEGMENTS", "DEMO_SEGMENTS"]

# Segment-exact, never substring: `src/contest/` is not a test directory.
# Both singular and plural because repositories use both.
TEST_SEGMENTS = frozenset({"test", "tests", "spec", "specs", "__tests__",
                           "testing", "fixtures"})

# Demo and stub code shares a subsystem's vocabulary BY DESIGN while
# implementing none of it, so it matches strongly and answers nothing.
DEMO_SEGMENTS = frozenset({"example", "examples", "samples", "demo", "demos",
                           "benchmarks", "typing-examples"})

_TEST_TOKEN = re.compile(r"(^|[._-])(test|spec)s?([._-]|$)")


def is_test(relpath: str) -> bool:
    """Two signals: a directory named for tests, or a filename that says so.

    The filename check is token-ish rather than substring so `foo_test.go`,
    `test_foo.py` and `foo.spec.ts` all match while `inspect.py` and
    `protest.py` do not.
    """
    parts = relpath.lower().split("/")
    if any(part in TEST_SEGMENTS for part in parts[:-1]):
        return True
    return any(_TEST_TOKEN.search(part.rsplit(".", 1)[0]) for part in parts)


def is_demo(relpath: str) -> bool:
    return any(part in DEMO_SEGMENTS for part in relpath.lower().split("/")[:-1])


def under(relpath: str, path_filter: str) -> bool:
    """Whether a path is the filter itself or lives beneath it.

    Directory-boundary aware, so scoping to `src/dispatch` never pulls in
    `src/dispatcher.ts` — a prefix match there would silently widen a scope the
    caller asked to narrow.
    """
    if not path_filter:
        return True
    stem = path_filter.rstrip("/")
    return relpath == stem or relpath.startswith(f"{stem}/")


def ident_tokens(text: str) -> set[str]:
    """Identifier-aware tokens: camelCase and snake_case split, short ones cut.

    Below four characters a token is almost always noise (`id`, `get`, `to`),
    and noise in this set turns a lexical boost into a uniform one.
    """
    out: set[str] = set()
    for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text):
        for part in re.split(r"_+", word):
            for piece in re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+", part):
                if len(piece) >= 4:
                    out.add(piece.lower())
    return out
