"""A quote too long to print keeps its HEAD and its TAIL, never just the head.

MEASURED, and both agents of the same round reported it independently. Told to
insert a sibling `describe` AFTER a 157-line block, the render cut the quote at
line 40 — so the closing `end`, the one line the instruction depended on, was
not in the answer at all. One agent inverted the operation to anchor on the
block's opening instead; the other, editing inside a `try:`, never saw the
`except` clause and had to reason around a handler it could not read.

Their own proposal, and it is strictly cheaper than what they got: first lines,
a marker naming how many were dropped, last lines. A block's end carries the
`end`, the `return`, the closing brace — the part an address needs most.
"""

from __future__ import annotations

from megabrain.ask._elide import MAX_QUOTE_LINES, elide

LONG = [f"line {n}" for n in range(1, 121)]


def test_a_short_quote_is_untouched() -> None:
    """Nothing is elided that fits. The marker is a cost, not a decoration."""
    assert elide(["a", "b", "c"], 1) == (["a", "b", "c"], "")


def test_a_long_quote_keeps_its_FIRST_and_LAST_lines() -> None:
    """The measured failure: the tail is where the block closes."""
    shown, note = elide(LONG, 1)
    assert shown[0] == "line 1"
    assert shown[-1] == "line 120", "dropped the closing lines of the block"


def test_the_elision_says_HOW_MANY_lines_it_dropped() -> None:
    """A gap with no count reads as "this is the whole thing" — the reader has
    to notice the line numbers disagree to find out otherwise."""
    shown, note = elide(LONG, 1)
    assert any("elided" in line for line in shown)
    assert any(str(120 - MAX_QUOTE_LINES) in line for line in shown)


def test_the_elision_marker_carries_the_REAL_line_numbers() -> None:
    """So a reader who needs the middle knows exactly what to open, and the
    numbers are the file's own, not the quote's offsets."""
    shown, _ = elide(LONG, 500)
    gap = next(line for line in shown if "elided" in line)
    # 120 lines from L500, 28 of head kept: the gap runs L528-L607.
    assert "528" in gap and "607" in gap


def test_no_more_lines_are_printed_than_the_CAP() -> None:
    """The cap is why this exists. Head plus tail plus the marker stays within
    it, or the elision costs more than the quote it shortens."""
    shown, _ = elide(LONG, 1)
    assert len(shown) <= MAX_QUOTE_LINES + 1
