"""The split-then-merge policy (the cAST recipe).

Two failures the policy exists to prevent: a chunk so small it carries no
context, and a chunk so large its embedding averages several unrelated ideas
into one meaningless direction. The budget is measured in NON-whitespace
characters, so deeply indented code is not punished for its indentation.
"""

from __future__ import annotations

from megabrain.chunkers import Chunker
from tests.unit.chunkers.fake import parser_for, source_of

BUDGET = 400          # small, so a test can reach it with readable fixtures


def _chunk(units: list[tuple[int, int, str, str]], total: int, *,
           children: dict[str, list[tuple[int, int, str, str]]] | None = None,
           repo: str = "") -> list:
    parser = parser_for(units, children=children)
    return Chunker(parser, repo=repo, budget=BUDGET).chunk_file(
        "a.py", source_of(total)).chunks


def test_small_neighbours_merge_into_one_chunk() -> None:
    """Three one-line functions are one idea, not three retrieval results."""
    chunks = _chunk([(1, 2, "function", "a"), (3, 4, "function", "b"),
                     (5, 6, "function", "c")], 6)
    assert len(chunks) == 1
    assert chunks[0].start_line == 1 and chunks[0].end_line == 6


def test_merging_stops_at_the_budget() -> None:
    chunks = _chunk([(1, 40, "function", "a"), (41, 80, "function", "b")], 80)
    assert len(chunks) == 2, "two budget-filling units must not merge"


def test_a_merged_chunk_names_everything_it_holds() -> None:
    """The name is what a reader scans; hiding two of three functions behind
    the first one's name makes the result look wrong."""
    chunks = _chunk([(1, 2, "function", "a"), (3, 4, "function", "b")], 4)
    assert chunks[0].name is not None
    assert "a" in chunks[0].name and "b" in chunks[0].name


def test_an_oversized_class_splits_into_header_plus_methods() -> None:
    """The header (fields, docstring, decorators) is its own retrievable unit:
    a question about the class's SHAPE should not return its longest method."""
    units = [(1, 200, "class", "Service")]
    children = {"Service": [(10, 100, "method", "handle"), (101, 200, "method", "close")]}
    chunks = _chunk(units, 200, children=children)
    kinds = [c.kind for c in chunks]
    assert "class_header" in kinds
    names = [c.name for c in chunks]
    assert "Service.handle" in names and "Service.close" in names


def test_an_oversized_function_splits_into_numbered_parts() -> None:
    """No inner structure to cut on, so the parts are numbered — `part` tells a
    reader the chunk is a fragment rather than the whole function."""
    chunks = _chunk([(1, 300, "function", "big")], 300)
    assert len(chunks) > 1
    assert all(c.part for c in chunks)
    assert chunks[0].part == f"1/{len(chunks)}"
    assert all(c.name == "big" for c in chunks)


def test_no_chunk_survives_over_budget() -> None:
    """The budget is a guarantee, not a preference.

    Every path out of the splitter has to respect it, including the leftovers:
    a container splits at its members, and the region BEFORE the first member —
    a long docstring, a wall of constants, a generated table — is a leftover
    that can easily be larger than everything it precedes.
    """
    from megabrain.chunkers import nws

    units = [(1, 600, "class", "Config")]
    children = {"Config": [(500, 600, "method", "load")]}   # 499 lines of header
    for chunk in _chunk(units, 600, children=children):
        assert nws(chunk.text) <= BUDGET, f"{chunk.kind} {chunk.name} escaped the budget"


def test_a_trailing_leftover_is_split_too() -> None:
    """The same leftover, on the other side of the last member."""
    from megabrain.chunkers import nws

    units = [(1, 600, "class", "Config")]
    children = {"Config": [(2, 40, "method", "load")]}      # 560 lines after it
    for chunk in _chunk(units, 600, children=children):
        assert nws(chunk.text) <= BUDGET


def test_splitting_accounts_for_weight_not_line_count() -> None:
    """Lines are not equal, so cutting a big unit into equal LINE counts does
    not produce equal chunks.

    One generated table, one minified import, one long string literal — a
    single line can outweigh a hundred around it, and a naive by-line split
    hands the whole weight to one piece.
    """
    from megabrain.chunkers import Chunker, nws
    from tests.unit.chunkers.fake import parser_for

    # Each heavy line fits on its own; two of them together do not. A by-line
    # split into halves would put both in the first piece.
    heavy = "x" * (BUDGET - 100)
    source = "".join((heavy if n in (3, 4) else "s") + "\n" for n in range(1, 21))
    chunks = Chunker(parser_for([(1, 20, "function", "f")]),
                     budget=BUDGET).chunk_file("a.py", source).chunks
    assert all(nws(c.text) <= BUDGET for c in chunks), [nws(c.text) for c in chunks]


def test_a_single_line_over_budget_is_irreducible_not_dropped() -> None:
    """Chunks are a partition of LINES, so a line larger than the budget cannot
    be cut — splitting mid-line would break the invariant that matters more.
    It is emitted whole and alone, never silently discarded.
    """
    from megabrain.chunkers import Chunker, nws, validate_partition
    from tests.unit.chunkers.fake import parser_for

    source = "small\n" + "y" * (BUDGET * 3) + "\nsmall\n"
    result = Chunker(parser_for([(1, 3, "function", "f")]),
                     budget=BUDGET).chunk_file("a.py", source)
    assert validate_partition(result) == []
    oversized = [c for c in result.chunks if nws(c.text) > BUDGET]
    assert len(oversized) == 1
    assert oversized[0].start_line == oversized[0].end_line, "an oversized chunk must be one line"


def test_every_chunk_carries_a_breadcrumb() -> None:
    """The breadcrumb is prepended to the embedded text, so a method body that
    never repeats its class name is still retrievable by it."""
    units = [(1, 10, "class", "Service")]
    chunks = _chunk(units, 10, children={"Service": [(2, 10, "method", "handle")]}, repo="acme")
    crumb = chunks[0].breadcrumb
    assert crumb.startswith("acme > a.py")
    assert "Service" in crumb


def test_nws_ignores_indentation() -> None:
    """Budget counts code, not layout."""
    from megabrain.chunkers import nws

    assert nws("    def f():\n        pass\n") == nws("def f():\npass\n")
