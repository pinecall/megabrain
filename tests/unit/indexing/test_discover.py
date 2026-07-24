"""What gets indexed, and what is deliberately left out.

Every exclusion here is a decision about what counts as "this repository's
code". Getting it wrong is expensive in both directions: indexing a vendored
tree buries the real source under a thousand near-matches, and skipping a real
directory makes code permanently unfindable with no error to notice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.indexing.discover import discover

EXTS = (".py", ".md")


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return tmp_path


def _found(root: Path, **kw: object) -> list[str]:
    return sorted(f.relpath for f in discover(root, EXTS, **kw))  # type: ignore[arg-type]


def test_finds_matching_extensions_only(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"a.py": "", "b.md": "", "c.png": "", "d.lock": ""})
    assert _found(root) == ["a.py", "b.md"]


def test_paths_are_posix_on_every_platform(tmp_path: Path) -> None:
    """Relpaths are the database keys and the engine matches them with "/".
    A backslash key on Windows corrupts the index in a way that only shows up
    as everything silently failing to match."""
    root = _repo(tmp_path, {"src/pkg/mod.py": ""})
    assert _found(root) == ["src/pkg/mod.py"]


@pytest.mark.parametrize("directory", ["node_modules", ".git", "__pycache__", "dist", ".venv"])
def test_build_and_vendor_directories_are_skipped(tmp_path: Path, directory: str) -> None:
    root = _repo(tmp_path, {"a.py": "", f"{directory}/b.py": ""})
    assert _found(root) == ["a.py"]


def test_agent_instruction_files_are_not_repository_content(tmp_path: Path) -> None:
    """These are context for whoever is READING the repo, not part of it. They
    also routinely contain prompts, which must never come back as this
    project's documentation."""
    root = _repo(tmp_path, {"a.py": "", "CLAUDE.md": "", "AGENTS.md": "", "README.md": ""})
    assert _found(root) == ["README.md", "a.py"]


def test_the_ignore_file_excludes_by_name_and_by_glob(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"a.py": "", "fixtures/b.py": "", "gen/c.py": "",
                            ".megabrainignore": "fixtures\ngen/*.py\n# a comment\n"})
    assert _found(root) == ["a.py"]


def test_a_bare_ignore_token_matches_any_segment(tmp_path: Path) -> None:
    """`fixtures` should mean "anywhere", not "at the root" — that is what
    someone writing one word into an ignore file means."""
    root = _repo(tmp_path, {"a.py": "", "deep/nested/fixtures/b.py": "",
                            ".megabrainignore": "fixtures\n"})
    assert _found(root) == ["a.py"]


def test_a_directory_prefix_does_not_match_a_similar_name(tmp_path: Path) -> None:
    """`src/disp` must not exclude `src/dispatcher.py`."""
    root = _repo(tmp_path, {"src/disp/a.py": "", "src/dispatcher.py": "",
                            ".megabrainignore": "src/disp\n"})
    assert _found(root) == ["src/dispatcher.py"]


def test_files_over_the_size_limit_are_skipped(tmp_path: Path) -> None:
    """A megabyte of generated data embeds into one meaningless direction and
    costs real money to do it."""
    root = _repo(tmp_path, {"small.py": "x", "huge.py": "x" * 700_000})
    assert _found(root) == ["small.py"]


def test_skips_are_reported_with_a_reason(tmp_path: Path) -> None:
    """A file that vanished from the index without explanation is the hardest
    kind of bug to notice, so discovery can always account for its choices."""
    root = _repo(tmp_path, {"a.py": "", "node_modules/b.py": "", "huge.py": "x" * 700_000})
    skipped = {s.relpath: s.reason for s in discover(root, EXTS).skipped}
    assert skipped == {"node_modules/b.py": "excluded", "huge.py": "too-big"}
