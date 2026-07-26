"""Transactional exact-string edits — the write half of the read→edit loop.

Ported from the previous engine, where this tool earned every one of its rules
in the field. Kept because the reason it exists has not changed: the host's
Edit requires a prior host Read of the same file, so every body megabrain has
already rendered gets paid for twice. That double payment is the token leak the
whole map/read design exists to kill.

Two-phase, and the order is the contract: validate EVERY op in memory against
the evolving text, and only if all of them pass does anything reach disk. A
half-applied batch is the one outcome a caller cannot recover from — they
cannot see which half.
"""

from __future__ import annotations

import pytest

from megabrain.edits import apply_edits, render_edits


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "util.py").write_text("def flatten(xs):\n    'Flatten one level.'\n",
                                      encoding="utf-8")
    (tmp_path / "auth").mkdir()
    (tmp_path / "auth" / "login.py").write_text("ok = n % 7 == 0\n", encoding="utf-8")
    return tmp_path


def test_a_batch_applies_across_FILES(repo) -> None:
    result = apply_edits(repo, [
        {"file": "util.py", "find": "Flatten one level.", "replace": "Flattened."},
        {"file": "auth/login.py", "find": "% 7 == 0", "replace": "% 11 == 0"},
    ])
    assert result["ok"] and sorted(result["written"]) == ["auth/login.py", "util.py"]
    assert "Flattened." in (repo / "util.py").read_text(encoding="utf-8")
    assert "% 11" in (repo / "auth" / "login.py").read_text(encoding="utf-8")


def test_ONE_failure_rolls_the_whole_batch_back(repo) -> None:
    """The rule the tool rests on. A batch that applied its first op and failed
    its second leaves a tree nobody can reason about."""
    before = (repo / "util.py").read_text(encoding="utf-8")
    result = apply_edits(repo, [
        {"file": "util.py", "find": "Flatten one level.", "replace": "CHANGED"},
        {"file": "util.py", "find": "TEXT THAT IS NOT THERE", "replace": "x"},
    ])
    assert not result["ok"] and result["written"] == []
    assert (repo / "util.py").read_text(encoding="utf-8") == before
    assert "NOTHING was written" in render_edits(result)


def test_text_not_found_names_the_NEAREST_line(repo) -> None:
    """The typo is usually whitespace or one identifier off. Seeing the real
    line unblocks the retry without spending another read on it."""
    result = apply_edits(repo, [
        {"file": "util.py", "find": "def flaten(xs):", "replace": "def f():"}])
    assert "Nearest line: L1" in result["report"][0]["error"]


def test_an_AMBIGUOUS_find_is_refused_until_it_is_made_unique(repo) -> None:
    """"the first occurrence" is not something the caller asked for, and not
    something they can see from where they are standing."""
    (repo / "dup.py").write_text("a = 1\nb = 2\na = 1\n", encoding="utf-8")
    result = apply_edits(repo, [{"file": "dup.py", "find": "a = 1", "replace": "a = 9"}])
    assert not result["ok"]
    assert "occurs 2 time(s), expected 1" in result["report"][0]["error"]

    result = apply_edits(repo, [{"file": "dup.py", "find": "a = 1",
                                 "replace": "a = 9", "count": 2}])
    assert result["ok"]
    assert (repo / "dup.py").read_text(encoding="utf-8").count("a = 9") == 2


def test_ops_on_the_same_file_see_each_others_RESULT(repo) -> None:
    """Validation runs on the evolving text, so a batch can edit a line and
    then edit what it just wrote — which is what makes a rename batch possible
    at all."""
    (repo / "seq.py").write_text("v = 1\n", encoding="utf-8")
    result = apply_edits(repo, [
        {"file": "seq.py", "find": "v = 1", "replace": "v = 2"},
        {"file": "seq.py", "find": "v = 2", "replace": "v = 3"},
    ])
    assert result["ok"]
    assert (repo / "seq.py").read_text(encoding="utf-8") == "v = 3\n"


def test_a_path_ESCAPING_the_repo_is_refused(repo) -> None:
    result = apply_edits(repo, [{"file": "../evil.py", "find": "x", "replace": "y"}])
    assert not result["ok"] and "escapes the repo" in result["report"][0]["error"]


def test_a_NEW_file_is_out_of_scope_and_says_so(repo) -> None:
    """replace edits what exists. Creating files is the host's Write, and an
    error that names it is what stops the caller retrying the same call."""
    result = apply_edits(repo, [{"file": "brand_new.py", "find": "x", "replace": "y"}])
    assert not result["ok"] and "Write" in result["report"][0]["error"]
    assert not (repo / "brand_new.py").exists()


def test_the_habitual_ALIASES_work(repo) -> None:
    """FIELD RUN (attrs#1549): an agent called this with {path, old, new} by
    habit — the host's Edit uses old_string/new_string — and it failed
    cryptically as "path escapes the repo: ''". The canonical names are
    file/find/replace; the aliases people actually type are accepted."""
    result = apply_edits(repo, [
        {"path": "util.py", "old": "Flatten one level.", "new": "Aliased."}])
    assert result["ok"] and "Aliased." in (repo / "util.py").read_text(encoding="utf-8")


def test_a_missing_file_field_NAMES_the_field(repo) -> None:
    """The same field run: the failure has to say which key is missing, not
    report a path escape for the empty string it built."""
    result = apply_edits(repo, [{"find": "x", "replace": "y"}])
    assert not result["ok"] and "missing 'file'" in result["report"][0]["error"]


def test_an_EMPTY_find_is_refused(repo) -> None:
    """`"".count("")` is not zero and `str.replace("", x)` rewrites every gap
    in the file — an empty find would pass validation and destroy the text."""
    result = apply_edits(repo, [{"file": "util.py", "find": "", "replace": "x"}])
    assert not result["ok"] and "empty find" in result["report"][0]["error"]


def test_success_tells_the_caller_to_run_the_GATES(repo) -> None:
    """The edit is not the end of the task. The render says so, because the
    next thing that should happen is a test run."""
    result = apply_edits(repo, [
        {"file": "util.py", "find": "Flatten one level.", "replace": "Done."}])
    assert "gates" in render_edits(result).lower()


def test_an_edit_that_BREAKS_the_syntax_is_refused(repo) -> None:
    """MEASURED: a generated batch inserted a guard inside a `try:` it never
    closed. The only thing between that and the working tree was an agent
    noticing — and this check is one the engine can run itself."""
    before = (repo / "util.py").read_text(encoding="utf-8")
    result = apply_edits(repo, [{"file": "util.py", "find": "def flatten(xs):",
                                 "replace": "def flatten(xs):\n    try:"}])
    assert not result["ok"] and "unparseable" in result["report"][0]["error"]
    assert (repo / "util.py").read_text(encoding="utf-8") == before


def test_a_file_that_ALREADY_did_not_parse_is_not_blocked(repo) -> None:
    """Fail-open, and this direction is the one that matters: otherwise a
    repository with one broken file becomes uneditable, and the edit that FIXES
    it is precisely the one refused."""
    (repo / "broken.py").write_text("def f(:\n    pass\n", encoding="utf-8")
    result = apply_edits(repo, [{"file": "broken.py", "find": "def f(:",
                                 "replace": "def f():"}])
    assert result["ok"], result["report"]
    assert (repo / "broken.py").read_text(encoding="utf-8").startswith("def f():")


def test_a_language_with_no_parser_is_not_blocked(repo) -> None:
    """The gate says "this got worse", never "I could not tell"."""
    (repo / "notes.xyz").write_text("anything at all\n", encoding="utf-8")
    result = apply_edits(repo, [{"file": "notes.xyz", "find": "anything",
                                 "replace": "{{{ unbalanced"}])
    assert result["ok"], result["report"]
