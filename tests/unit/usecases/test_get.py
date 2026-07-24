"""`get`: the file it hands back must BE the file.

Chunks partition a file by line — that invariant is checked at index time — so
putting them back together has to reproduce the source exactly. If it does not,
every line number after the first seam is wrong, and `--symbol` quietly returns
a window starting somewhere inside the previous definition.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.storage import Store
from megabrain.usecases import build_index, get_code
from tests.unit.indexing.fake import CountingEmbedder, write


def _wide_source() -> str:
    """Big enough to be cut into several chunks — the seams are the point.

    A file small enough to fit one chunk cannot show the bug: there is no
    boundary for a line to fall through.
    """
    blocks = []
    for n in range(12):
        body = "\n".join(f"    value_{n}_{i} = compute({i}) + offset_{n}" for i in range(20))
        blocks.append(f'def feature_{n}(offset_{n}):\n'
                      f'    """Feature number {n}."""\n{body}\n    return value_{n}_0\n')
    return "\n\n".join(blocks) + "\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, {"wide.py": _wide_source(), "small.py": "def one(): return 1\n"})
    build_index(tmp_path, embedder=CountingEmbedder())
    return tmp_path


def test_the_file_really_was_cut_into_several_chunks(repo: Path) -> None:
    """Anti-vacuum: if the fixture stopped producing seams, everything below
    would pass while testing nothing."""
    with Store(repo) as store:
        assert len(store.chunks.read_file("wide.py")) > 1


def test_the_returned_text_is_the_file_verbatim(repo: Path) -> None:
    view = get_code(repo, "wide.py")
    assert view["text"] == (repo / "wide.py").read_text(encoding="utf-8").rstrip("\n")


def test_the_line_count_survives_every_seam(repo: Path) -> None:
    """One line vanished per boundary: the chunks were concatenated as
    strings, so each chunk's last line was glued onto the next chunk's first.
    Six chunks, five lines gone, and every span after the first seam shifted."""
    on_disk = (repo / "wide.py").read_text(encoding="utf-8").rstrip("\n").count("\n") + 1
    view = get_code(repo, "wide.py")
    assert view["text"].count("\n") + 1 == on_disk
    assert view["end_line"] == on_disk


def test_a_symbol_starts_at_its_own_declaration(repo: Path) -> None:
    """The symptom that exposed it: `--symbol` on a late definition returned a
    window opening in the middle of the previous one."""
    view = get_code(repo, "wide.py", symbol="feature_9")
    assert view["text"].startswith("def feature_9("), view["text"][:60]
    assert view["text"].rstrip().endswith("return value_9_0")


def test_the_reported_span_matches_the_text(repo: Path) -> None:
    """A span that disagrees with its own body is worse than no span: it is
    what a reader pastes into an editor."""
    view = get_code(repo, "wide.py", symbol="feature_5")
    assert view["end_line"] - view["start_line"] + 1 == view["text"].count("\n") + 1


def test_an_unknown_symbol_says_so(repo: Path) -> None:
    with pytest.raises(KeyError, match="feature_99"):
        get_code(repo, "wide.py", symbol="feature_99")


def test_a_file_outside_the_index_is_not_invented(repo: Path) -> None:
    with pytest.raises(FileNotFoundError, match="nope.py"):
        get_code(repo, "nope.py")
