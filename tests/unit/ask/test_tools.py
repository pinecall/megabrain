"""Opening a file for the narrator — the capability a TASK needs.

Retrieval hands the narrator chunks chosen by cosine. That is the right input
for explaining a mechanism and the wrong one for changing it: a change has to
see the region it lands in, the style of its neighbours, and the line to type
on. Measured, the absence cost a whole round trip — the narrator answered "how
it works" and the agent had to come back with "and where is that defined?".

The file is reassembled FROM THE INDEX. Chunks are an exact line partition of
their file, so concatenating them in line order reproduces it — which is worth
proving here, because the whole feature rests on it.
"""

from __future__ import annotations

from megabrain.ask.tools import MAX_LINES, OPEN_FILE, open_file
from megabrain.chunkers.model import Chunk
from megabrain.storage import Store

SOURCE = "\n".join(f"line {n}" for n in range(1, 31))


def indexed(tmp_path, path: str = "lib/app.rb", source: str = SOURCE) -> Store:
    """A file stored as TWO chunks, the way the chunker would split it."""
    store = Store(tmp_path)
    store.files.upsert(path, "sha", "", None)
    lines = source.split("\n")
    half = len(lines) // 2
    store.chunks.insert([
        Chunk(file=path, kind="block", name="a", part=None, start_line=1,
              end_line=half, text="\n".join(lines[:half]), breadcrumb=path),
        Chunk(file=path, kind="block", name="b", part=None, start_line=half + 1,
              end_line=len(lines), text="\n".join(lines[half:]), breadcrumb=path),
    ], None)
    return store


def test_the_file_comes_back_WHOLE_from_its_chunks(tmp_path) -> None:
    """The partition invariant, used rather than merely asserted elsewhere."""
    with indexed(tmp_path) as store:
        out = open_file(store, "lib/app.rb")
    body = "\n".join(line[7:] for line in out.split("\n")[1:])   # 5-wide gutter + 2
    assert body == SOURCE


def test_every_line_carries_its_NUMBER(tmp_path) -> None:
    """"insert after line 322" is the whole point; without a gutter the model
    has to count, and it counts wrong."""
    with indexed(tmp_path) as store:
        out = open_file(store, "lib/app.rb")
    assert "    1  line 1" in out
    assert "   30  line 30" in out


def test_a_long_file_is_cut_LOUDLY_and_says_how_to_continue(tmp_path) -> None:
    """A silent cut would have the model reason about a file it believes it has
    read in full, and propose an edit to a line it never saw. Announcing the
    cut is half of it; naming the way back is what makes it recoverable."""
    long_source = "\n".join(f"line {n}" for n in range(1, MAX_LINES + 200))
    with indexed(tmp_path, source=long_source) as store:
        out = open_file(store, "lib/app.rb")
    assert f"showing L1-{MAX_LINES}" in out and "from_line" in out
    assert out.count("\n") <= MAX_LINES + 3


def test_a_RANGE_returns_only_that_region(tmp_path) -> None:
    """How a big file stays affordable: opening two files of a real repository
    in full spent 85 000 characters of context on code the edit never touched."""
    with indexed(tmp_path) as store:
        out = open_file(store, "lib/app.rb", 10, 12)
    assert "   10  line 10" in out and "   12  line 12" in out
    assert "line 9\n" not in out and "line 13" not in out


def test_a_WRONG_path_answers_with_the_near_misses(tmp_path) -> None:
    """The model guesses a path from prose more often than it copies one.
    "not found" ends the turn; a list of candidates continues it."""
    with indexed(tmp_path) as store:
        out = open_file(store, "app.rb")
    assert "lib/app.rb" in out and "Did you mean" in out


def test_a_path_matching_NOTHING_says_how_paths_work(tmp_path) -> None:
    with indexed(tmp_path) as store:
        out = open_file(store, "src/totally/elsewhere.py")
    assert "repository-relative" in out


def test_the_tool_schema_names_the_TEST_file_too() -> None:
    """The measured failure was a task whose edit surface was two files: the
    implementation and its test. A description that only asks for "the file"
    gets one of them."""
    description = OPEN_FILE["function"]["description"]        # type: ignore[index]
    assert "test" in str(description).lower()
