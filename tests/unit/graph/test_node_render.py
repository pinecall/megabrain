"""The node render: one row per FILE, and never the code.

The count above each list is what an agent reads to decide whether a change is
contained. A file that both imports and calls another is ONE dependant; listed
twice it reads as two, and "imported by (8)" for four files is a number that
argues against acting — the same reason `views._links` joins kinds per pair.
"""

from __future__ import annotations

from megabrain.contracts import NodeEdge, NodeView, SemanticTie
from megabrain.graph.render import render_node
from megabrain.storage.rows import SymbolRow


def _view(**over: object) -> NodeView:
    base = NodeView(
        repo="r", file="a.py", resolved_from="a.py", community=3,
        community_label="Community 3", degree=2,
        imports=[NodeEdge(file="b.py", kind="import")],
        imported_by=[NodeEdge(file="c.py", kind="call"),
                     NodeEdge(file="c.py", kind="import")],
        semantic=[SemanticTie(file="twin.py", score=0.91)],
        symbols=[SymbolRow(file="a.py", name="run", kind="function", line=3,
                           end_line=9, signature="def run()")],
        ms=1)
    return {**base, **over}  # type: ignore[typeddict-item,return-value]


def test_one_row_per_file_with_its_kinds_joined() -> None:
    text = render_node(_view())
    assert "imported by (1)" in text, "two edges to one file are one dependant"
    assert "c.py  [call/import]" in text


def test_both_directions_and_the_twins_are_shown() -> None:
    text = render_node(_view())
    assert "imports (1)" in text and "b.py" in text
    assert "twin.py" in text and "0.91" in text


def test_symbols_carry_real_line_ranges() -> None:
    assert "L3-9  function run" in render_node(_view())


def test_an_empty_section_says_none_rather_than_vanishing() -> None:
    """A missing heading reads as "not checked"; `none` is a finding — it is
    how "nothing depends on this" (dead code) reaches the caller."""
    text = render_node(_view(imported_by=[], semantic=[]))
    assert "imported by: none" in text
    assert "semantic twins" in text
