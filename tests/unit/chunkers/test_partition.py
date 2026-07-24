"""The partition invariant: every line of a file belongs to exactly one chunk.

This is the engine's hardest rule, and it is what makes retrieval trustworthy —
a gap means code that can never be found, an overlap means the same code found
twice under two different scores. `validate_partition` is the oracle, and it is
the same one that decides whether a generated chunker is allowed to install.
"""

from __future__ import annotations

import pytest

from megabrain.chunkers import Chunker, validate_partition
from tests.unit.chunkers.fake import parser_for, source_of


@pytest.mark.parametrize("total", [1, 2, 17, 400])
def test_chunks_cover_every_line_exactly_once(total: int) -> None:
    result = Chunker(parser_for([(1, total, "function", "f")])).chunk_file(
        "a.py", source_of(total))
    assert validate_partition(result) == []
    covered = [ln for c in result.chunks for ln in range(c.start_line, c.end_line + 1)]
    assert covered == list(range(1, total + 1))


def test_an_empty_file_yields_no_chunks_and_still_validates() -> None:
    result = Chunker(parser_for([])).chunk_file("empty.py", "")
    assert result.chunks == []
    assert validate_partition(result) == []


def test_a_file_with_no_units_is_still_fully_covered() -> None:
    """A parser that recognises nothing — a config file, an unparseable
    source — must not drop the file from the index."""
    result = Chunker(parser_for([])).chunk_file("data.py", source_of(30))
    assert validate_partition(result) == []
    assert sum(c.end_line - c.start_line + 1 for c in result.chunks) == 30


def test_the_gap_before_a_unit_belongs_to_it() -> None:
    """Comments and blank lines above a definition are ABOUT that definition:
    a docstring banner separated from its function is noise in both places."""
    result = Chunker(parser_for([(5, 9, "function", "f")])).chunk_file(
        "a.py", source_of(9))
    assert validate_partition(result) == []
    owner = next(c for c in result.chunks if c.name == "f")
    assert owner.start_line == 1, "leading comment gap was not attached"


def test_trailing_lines_after_the_last_unit_are_kept() -> None:
    result = Chunker(parser_for([(1, 5, "function", "f")])).chunk_file(
        "a.py", source_of(12))
    assert validate_partition(result) == []
    assert max(c.end_line for c in result.chunks) == 12


def test_a_parse_failure_still_partitions() -> None:
    """A file the parser choked on falls back to line windows rather than
    vanishing. Being findable with poor boundaries beats not being findable."""
    result = Chunker(parser_for([], ok=False)).chunk_file("broken.py", source_of(250))
    assert result.parse_ok is False
    assert validate_partition(result) == []
    assert result.chunks, "an unparseable file must still be indexed"


def test_validate_partition_detects_a_gap() -> None:
    """Anti-vacuum: an oracle that accepts everything proves nothing."""
    from megabrain.chunkers import Chunk, FileResult

    def chunk(start: int, end: int) -> Chunk:
        return Chunk(file="a.py", kind="block", name=None, start_line=start,
                     end_line=end, text="", breadcrumb="")

    assert validate_partition(FileResult("a.py", [chunk(1, 3), chunk(5, 9)], [], "", True, 9))
    assert validate_partition(FileResult("a.py", [chunk(1, 5), chunk(4, 9)], [], "", True, 9))
    assert validate_partition(FileResult("a.py", [chunk(1, 5)], [], "", True, 9))
