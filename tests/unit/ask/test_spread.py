"""How many rows a lane returns, and which ones go when there are too many.

MEASURED, and it was a defect introduced by making the extractor BETTER. Once
mocha cases became symbols, express's test files started contributing rows — and
three of five ordinary tasks went from a useful render to NOTHING, because the
cap emptied instead of trimming:

    add res.inline beside res.attachment      37 sites
    make res.sendFile handle a missing root    0     <- 3 code + 44 tests
    add a maxAge option to res.cookie          0     <- 12 code + 29 tests
    let res.redirect accept a status object    0     <- 8 code + 39 tests

A better index made the answer worse, which is the shape of bug worth a test.
"""

from __future__ import annotations

from megabrain.ask.sites.spread import MAX_ROWS, MAX_SPREAD, MAX_TESTS, merged


def code(path: str, count: int, start: int = 1):
    return [((path, f"fn{n}", n, n), False) for n in range(start, start + count)]


def suite(path: str, count: int, start: int = 100):
    return [((path, f"it case {n}", n, n), True) for n in range(start, start + count)]


def test_ALL_the_implementation_survives_a_suite_that_dwarfs_it() -> None:
    """The measured case: `sendFile` is three implementation sites and 44 test
    cases, and the three are where the edit goes."""
    got = merged({"sendFile": code("lib/response.js", 3) + suite("test/x.js", 44)})
    assert [row[1] for row in got if not row[1].startswith("it ")] == \
        ["fn1", "fn2", "fn3"]


def test_the_suite_is_SAMPLED_not_dropped_and_not_pasted_whole() -> None:
    """A pattern to imitate needs one example, not forty-four — but zero
    examples is what the all-or-nothing cap gave."""
    got = merged({"sendFile": code("lib/response.js", 3) + suite("test/x.js", 44)})
    cases = [row for row in got if row[1].startswith("it ")]
    assert len(cases) == MAX_TESTS


def test_a_BROAD_name_no_longer_silences_a_specific_one() -> None:
    """"a name in forty places is the repository's idiom" is a property of the
    NAME. Judged over the union, the broad one took the narrow one down too."""
    got = merged({"resolve_envvar_value": code("lib/response.js", 8),
                  "get_help_record": code("lib/response.js", 90, start=500)})
    assert [row for row in got if row[2] < 100], "the narrow name survives"
    assert not [row for row in got if row[2] >= 500], "the broad one is vocabulary"


def test_a_ONE_WORD_name_gets_a_TIGHTER_budget_than_a_specific_one() -> None:
    """MEASURED on click, and it is the regression that admitting one-word names
    introduced. `Option` is declared, so the index vouches for it — and it
    resolves to 10 implementation sites, contributing 10 rows of noise beside
    `show_envvar`'s 3. The one-word names that WERE the target resolve to one or
    two. Same site count, opposite verdict, decided by the name's own shape."""
    assert not merged({"Option": code("src/click/core.py", 10)}), "the container"
    assert merged({"attachment": code("lib/response.js", 1)}), "the target"
    assert merged({"resolve_envvar_value": code("src/click/core.py", 10)}), \
        "a specific name keeps the wide budget — ten sites of it is a real trace"


def test_vocabulary_is_judged_on_CODE_sites_only() -> None:
    """The distinction that was the bug: counting the union called the most
    specific name in the task vocabulary because its suite was thorough."""
    thorough = code("lib/a.js", 2) + suite("test/a.js", MAX_SPREAD + 20)
    assert merged({"sendFile": thorough}), "two code sites is not vocabulary"


def test_the_MOST_SPECIFIC_name_is_served_first() -> None:
    """A trim should cost the reader the least informative row, not whichever
    name sorted last alphabetically."""
    got = merged({"aaa_broad": code("lib/broad.js", MAX_ROWS),
                  "zzz_narrow": code("lib/narrow.js", 2)})
    assert got[0][0] == "lib/narrow.js"


def test_the_TOTAL_is_capped_so_a_render_stays_a_place_to_jump() -> None:
    got = merged({f"ident_number_{i}": code(f"lib/{i}.js", 30) for i in range(5)})
    assert len(got) == MAX_ROWS


def test_the_sample_prefers_the_suite_NAMED_after_the_identifier() -> None:
    """For `cookie`, `test/res.cookie.js` before the four other suites that
    merely send one — the sample should be of the thing asked about."""
    got = merged({"cookie": suite("test/res.send.js", 10, start=200)
                  + suite("test/res.cookie.js", 10, start=300)})
    assert all(row[0] == "test/res.cookie.js" for row in got)


def test_a_name_living_only_in_tests_still_answers() -> None:
    """No implementation is a real finding — the helper may not exist yet — and
    the suite is then the only place to look."""
    assert merged({"inline": suite("test/res.inline.js", 3)})
