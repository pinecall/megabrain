"""`.gitignore` decides what is not this repository's source.

MEASURED across the machine's indexed repos, and it was the largest single source
of noise in a render. shipway compiles TypeScript into `bin/`, which its own
`.gitignore` declares under "# Build output" — 122 of 196 indexed files were that
output, so every `src/` symbol had a compiled twin and one site returned two
rows. aldus contributed `dist-lib-types/*.d.ts`; pinecall/sdk contributed
`src.bkp/`, a snapshot of old code competing with the live version.

`Excluder`'s list cannot fix this: it is universal on purpose, and `bin/` holds
real code in a Python or Rust project. The repo already answered for its own
layout.
"""

from __future__ import annotations

import subprocess

from megabrain.indexing._gitignore import git_ignored
from megabrain.indexing.discover import discover
from megabrain.project import load_project


def repo(tmp_path, ignore: str = "bin/\n"):
    """A real git repository, because the filter delegates to real git."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text(ignore, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "bin").mkdir()
    (tmp_path / "src" / "app.py").write_text("def live(): pass\n", encoding="utf-8")
    (tmp_path / "bin" / "app.py").write_text("def compiled(): pass\n", encoding="utf-8")
    return tmp_path


def test_BUILD_OUTPUT_the_repo_declares_is_not_indexed(tmp_path) -> None:
    """The measured case: `src/app.py` and its `bin/` twin both indexed meant a
    grep for one site returned two, one of them generated."""
    found = discover(repo(tmp_path), [".py"])
    assert [f.relpath for f in found.files] == ["src/app.py"]


def test_the_skip_is_RECORDED_with_its_reason(tmp_path) -> None:
    """This module's own rule: "a file that vanished from the index without
    explanation is the hardest kind of bug to notice"."""
    found = discover(repo(tmp_path), [".py"])
    assert [(s.relpath, s.reason) for s in found.skipped] == [("bin/app.py", "gitignored")]


def test_a_repo_can_TURN_IT_OFF_because_the_heuristic_has_a_false_positive(
        tmp_path) -> None:
    """Found in megabrain-v2 itself: `evals/` is gitignored and IS source. The
    escape is a committed field so whoever clones the repo inherits the answer."""
    root = repo(tmp_path)
    (root / "megabrain.json").write_text('{"gitignore": false}', encoding="utf-8")
    assert load_project(root).gitignore is False
    assert {f.relpath for f in discover(root, [".py"])} == {"src/app.py", "bin/app.py"}


def test_the_default_is_ON_and_only_an_explicit_false_disables_it(tmp_path) -> None:
    """A typo must not silently widen the index back out with nothing to show it."""
    root = repo(tmp_path)
    (root / "megabrain.json").write_text('{"gitignore": "no"}', encoding="utf-8")
    assert load_project(root).gitignore is True


def test_gitignore_NEGATION_is_honoured_because_git_answers_not_us(tmp_path) -> None:
    """`!src/keep.py` after a glob that would have caught it.

    Written the other way round first and it failed, which is the argument for
    this file: git will NOT re-include a file whose parent DIRECTORY is excluded,
    so `bin/` plus `!bin/keep.py` keeps the file ignored. A hand-rolled matcher
    would have honoured the negation and indexed a build artifact — the rule is
    real, documented, and not one anybody reimplements correctly by accident.
    """
    root = repo(tmp_path, ignore="*.gen.py\n!src/keep.gen.py\n")
    (root / "src" / "keep.gen.py").write_text("def kept(): pass\n", encoding="utf-8")
    (root / "src" / "drop.gen.py").write_text("def dropped(): pass\n", encoding="utf-8")
    found = {f.relpath for f in discover(root, [".py"])}
    assert "src/keep.gen.py" in found
    assert "src/drop.gen.py" not in found


def test_a_NON_GIT_directory_indexes_everything(tmp_path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert git_ignored(tmp_path, ["a.py"]) == frozenset()
    assert {f.relpath for f in discover(tmp_path, [".py"])} == {"a.py"}


def test_it_fails_OPEN_when_git_cannot_answer(tmp_path, monkeypatch) -> None:
    """Losing the filter costs precision; losing the index costs the tool. So a
    missing or hung git yields an empty set, never an exception."""
    root = repo(tmp_path)          # built BEFORE git is taken away

    def explode(*_args, **_kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(subprocess, "run", explode)
    assert git_ignored(root, ["bin/app.py"]) == frozenset()


def test_a_git_FAILURE_code_is_not_read_as_a_list_of_files(tmp_path, monkeypatch) -> None:
    """Exit 1 means "nothing matched" and is normal; 128 means "not a work tree".
    Reading stdout on a real failure would drop files for the wrong reason."""
    class Failed:
        returncode, stdout, stderr = 128, "src/app.py\n", "fatal: not a git repository"

    root = repo(tmp_path)          # built BEFORE git is replaced
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: Failed())
    assert git_ignored(root, ["src/app.py"]) == frozenset()
