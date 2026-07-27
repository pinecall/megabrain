"""How many rows a lane may return, and which ones go when there are too many.

MEASURED, and it was a defect I introduced by making the extractor better. Once
mocha cases became symbols, express's test files started contributing rows — and
three of five ordinary tasks went from a useful render to NOTHING, because the
cap was all-or-nothing: `return hits if len(hits) <= MAX_SPREAD else []`.

Two rules replace it, and the first is the one the original docstring already
argued for without implementing: "a name in forty places is the repository's
idiom, not this task's target" is a property of the NAME. Judged per name, a
task saying `res.redirect` keeps `redirect` and discards `status`; judged over
the union, `status` silenced `redirect` too.

The second is that a cap TRUNCATES rather than empties. Specific names are
served first — a name resolving to three sites says more about the task than one
resolving to thirty — so the rows that survive a trim are the ones worth having,
and an over-broad task degrades into a shorter answer instead of a blank one.
"""

from __future__ import annotations

from .idents import specific

__all__ = ["merged", "MAX_SPREAD", "MAX_BARE", "MAX_ROWS", "MAX_TESTS"]

Site = tuple[str, str, int, int]

MAX_SPREAD = 40
"""IMPLEMENTATION sites one identifier may have before it is vocabulary.

Counted over code only, and that distinction is the measurement: in express
`sendFile` resolves to 47 sites — THREE of them implementation and 44 of them
test cases. Counting the union called the most specific name in the task
"vocabulary" and dropped it."""

MAX_BARE = 6
"""Implementation sites a name the INDEX vouched for may have — see `specific`.

A one-word name is admitted because the repo declares it, and that admission
cannot tell a target from its container. The site count can: MEASURED, `Option`
resolves to 10 implementation sites in click and contributed 10 rows of noise
beside `show_envvar`'s 3, while the one-word names that WERE the target resolve
to one or two (`attachment` 1, `inline` 1, express's `render` 5). Six splits
those cleanly — and it is tuned on three repositories, so it is a threshold,
not a law."""

MAX_TESTS = 4
"""Test cases kept per identifier.

All of the implementation and a SAMPLE of the tests, because the two answer
different questions: the implementation sites are where the edit goes and there
are three of them, while the tests are a pattern to imitate and the reader needs
one, not the forty-four that would bury the three."""

MAX_ROWS = 40
"""Rows the whole lane may return, most specific name first.

A render longer than this stops being a place to jump and becomes a file to
read, which is the thing `grep` already did badly."""


def merged(per_name: dict[str, list[tuple[Site, bool]]]) -> list[Site]:
    """Every name's sites under its quota, specific names first, deduplicated.

    Sorted by how much implementation the name resolved to, so the trim falls on
    the broadest name rather than on whichever one happened to be alphabetically
    last — the row a reader loses should be the least informative one.
    """
    chosen = {name: _quota(name, rows) for name, rows in per_name.items()}
    out: list[Site] = []
    for _, sites in sorted(chosen.items(), key=lambda pair: (len(pair[1]), pair[0])):
        for site in sites:
            if site not in out:
                out.append(site)
        if len(out) >= MAX_ROWS:
            return out[:MAX_ROWS]
    return out


def _quota(name: str, rows: list[tuple[Site, bool]]) -> list[Site]:
    """One identifier's rows: all the code, the nearest few tests, or nothing.

    The tests are ordered by whether the file is named after the identifier
    first, which for `cookie` puts `test/res.cookie.js` ahead of the four other
    suites that merely send one — the sample should be of the thing asked about.
    """
    code = [site for site, is_test in rows if not is_test]
    if len(code) > (MAX_SPREAD if specific(name) else MAX_BARE):
        return []
    tests = sorted((site for site, is_test in rows if is_test),
                   key=lambda site: (name not in site[0], site[0], site[2]))
    return code + tests[:MAX_TESTS]
