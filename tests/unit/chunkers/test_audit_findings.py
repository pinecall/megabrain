"""Regression pins from the corpus audit — each one reproduced before fixing.

The pattern behind all four: green unit tests, wrong output on real code. The
partition oracle checks line arithmetic, not text or size, so everything here
hid behind it.
"""

from __future__ import annotations

from megabrain.chunkers import Chunker, nws, validate_partition
from megabrain.chunkers._balance import balance
from megabrain.chunkers.python import parse
from tests.unit.chunkers.fake import parser_for, source_of

BUDGET = 400


def test_balance_never_leaves_a_foldable_orphan() -> None:
    """The half of the split fix that was missing.

    Eager cutting at `running >= target` overshoots by up to a line per piece;
    the accumulated overshoot leaves a sub-target remainder as its own part —
    and merge is forbidden from touching parts, so the no-signal fragment both
    docstrings promise to avoid ships anyway. Proven on a real corpus: a
    part 3/3 whose entire text was `)` — one character, embedded alone.

    The property: no ADJACENT pair of returned pieces may be foldable within
    the budget. That is exactly the guarantee merge provides for everything
    else, restated for the one region merge is banned from.
    """
    weights = [1] * 100
    pieces = balance(1, weights, budget=34)
    sums = [sum(weights[start - 1:end]) for start, end in pieces]
    for left, right in zip(sums, sums[1:]):
        assert left + right > 34, f"foldable neighbours survived: {sums}"


def test_a_split_function_has_no_one_line_tail() -> None:
    """The same property end to end through the Chunker."""
    chunks = Chunker(parser_for([(1, 100, "function", "big")]),
                     budget=BUDGET).chunk_file("a.py", source_of(100)).chunks
    parts = [c for c in chunks if c.part]
    assert len(parts) > 1
    weights = [nws(c.text) for c in parts]
    for left, right in zip(weights, weights[1:]):
        assert left + right > BUDGET, f"foldable tail fragment: {weights}"


def test_exotic_line_breaks_do_not_corrupt_text_or_desync_lines() -> None:
    """`str.splitlines()` breaks on \\f, \\v, \\x1c and friends; `ast` counts
    physical lines by \\n only.

    A form feed inside a string literal (a legal PEP-8 page separator) made
    the two disagree: the stored chunk text had the \\f rewritten to \\n —
    silent corruption of 'the stored text stays verbatim' — and every symbol
    after it pointed one line off from its chunk.
    """
    source = 'def f():\n    x = "a\fb"\n    return x\n'
    result = Chunker(parse).chunk_file("weird.py", source)
    assert validate_partition(result) == []
    rebuilt = "\n".join(c.text for c in sorted(result.chunks, key=lambda c: c.start_line))
    assert "a\fb" in rebuilt, "the form feed was rewritten"
    # ast's view and the chunker's view of line count must agree.
    assert result.total_lines == source.count("\n")


def test_typed_module_constants_are_symbols() -> None:
    """`MAX: int = 10` vanished from the symbol table while `PLAIN = 3`
    survived — a parity regression: `X: Final = ...` is the house style of
    the reference SDK itself, so the lexical lane lost every typed constant.
    """
    parsed = parse("cfg.py", "MAX: int = 10\nNAMES: list[str] = []\nPLAIN = 3\n")
    names = {s.name for s in parsed.symbols}
    assert {"MAX", "NAMES", "PLAIN"} <= names, f"missing from: {names}"


def test_renumber_numbers_non_adjacent_runs_independently() -> None:
    """A class with two large leftover regions (before its member and after
    it) had ALL header fragments numbered as one 1/6..6/6 run — with the
    member sitting between part 3 and part 4. The labels claimed a contiguity
    that does not exist.
    """
    units = [(1, 300, "class", "C")]
    children = {"C": [(140, 160, "method", "m")]}   # heavy regions both sides
    chunks = Chunker(parser_for(units, children=children),
                     budget=BUDGET).chunk_file("a.py", source_of(300)).chunks
    header_parts = [c for c in chunks if c.kind == "class_header" and c.part]
    assert header_parts, "expected split headers"
    # Fragments before the member and after it are separate runs: each run's
    # numbering must be self-consistent (k/n with n = run length), and no run
    # may span the member.
    runs: list[list] = [[]]
    for c in sorted(chunks, key=lambda c: c.start_line):
        if c.kind == "class_header" and c.part:
            runs[-1].append(c)
        elif runs[-1]:
            runs.append([])
    runs = [r for r in runs if r]
    assert len(runs) == 2, "the member did not split the header fragments"
    for run in runs:
        n = len(run)
        assert [c.part for c in run] == [f"{k}/{n}" for k in range(1, n + 1)], \
            [c.part for c in run]
