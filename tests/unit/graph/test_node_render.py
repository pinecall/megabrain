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


# ── what real repositories broke ─────────────────────────────────────────

def test_source_dependants_outrank_tests_and_docs() -> None:
    """MEASURED on fastapi: `routing.py` has 96 dependants of which FOUR are
    source — the rest are `tests/` and `docs_src/`. Sorted by path, the cap
    dropped 56 rows by ALPHABET, so in a repo whose source sorts late ("src/")
    the four that decide whether a change is safe are exactly what falls off.
    """
    edges = [NodeEdge(file=f"spec/models/m{n:02d}_spec.rb", kind="call")
             for n in range(60)]
    edges += [NodeEdge(file="src/app.rb", kind="import")]
    text = render_node(_view(file="src/user.rb", imported_by=edges))
    body = text[text.index("imported by"):]
    assert "src/app.rb" in body, "the one source dependant must survive the cap"
    assert body.index("src/app.rb") < body.index("spec/models/m00_spec.rb")


def test_the_count_separates_source_from_tests() -> None:
    """`imported by (96)` and `4 source, 92 tests/docs` are different facts,
    and the second is the one that says whether a change is contained."""
    edges = [NodeEdge(file="src/app.py", kind="import"),
             NodeEdge(file="tests/test_a.py", kind="call"),
             NodeEdge(file="examples/demo.py", kind="import")]
    assert "imported by (3 — 1 source, 2 tests/examples)" in render_node(
        _view(imported_by=edges))


def test_a_language_with_no_edge_extractor_says_so() -> None:
    """THE bug this render could not survive: `post.rb` requires `user.rb`,
    and megabrain extracts no Ruby import graph — so the file read
    `imported by: none`, which this tool's own description calls dead code.
    Silence must not be reported as a finding."""
    text = render_node(_view(file="app/models/user.rb", imports=[], imported_by=[]))
    assert "imported by: none" not in text
    assert "imports: none" not in text
    assert "not extracted" in text
    assert "NOT evidence" in text


def test_a_language_WITH_an_extractor_still_reports_none_as_a_finding() -> None:
    """For Python, empty really does mean nothing depends on this."""
    text = render_node(_view(file="src/app.py", imported_by=[]))
    assert "imported by: none" in text


def test_the_symbol_outline_is_capped_well_under_the_edges() -> None:
    """`fastapi/routing.py` declares 156 symbols — 156 lines of the ONE thing
    the caller's own editor already gives them, in a tool whose whole rule is
    that it never bills for what a Read supplies."""
    many = [SymbolRow(file="a.py", name=f"f{n}", kind="function", line=n,
                      end_line=n, signature="") for n in range(200)]
    text = render_node(_view(symbols=many))
    assert "declares (200" in text
    outline = text[text.index("declares"):].splitlines()
    assert len(outline) <= 18, "the outline must not dominate what only it can say"
    assert "more" in outline[-1]


def test_a_pin_is_not_a_dependant() -> None:
    """MEASURED on fastapi: `routing.py` showed 96 "dependants", and rows whose
    only edge was `pins` — a test PINNING the file, not code importing it —
    were counted among them. "what breaks if I change this" and "what goes red"
    are different questions and deserve different counts."""
    edges = [NodeEdge(file="src/app.py", kind="import"),
             NodeEdge(file="tests/test_a.py", kind="pins"),
             NodeEdge(file="tests/test_b.py", kind="call/import".split("/")[0])]
    text = render_node(_view(imported_by=edges))
    assert "imported by (2" in text, "the pins-only row is not a dependant"
    assert "pinned by 1 test" in text
    assert "tests/test_a.py" in text


def test_a_file_only_pinned_still_reports_its_pins() -> None:
    edges = [NodeEdge(file="tests/test_a.py", kind="pins")]
    text = render_node(_view(imported_by=edges))
    assert "imported by: none" in text
    assert "pinned by 1 test" in text


def test_the_pin_list_is_a_COUNT_not_a_roster() -> None:
    """MEASURED: splitting pins out of the dependants made the render LONGER —
    44 test paths listed. If you are changing the file you will run the suite,
    not read the names; the count is the actionable half."""
    edges = [NodeEdge(file=f"tests/test_{n:02d}.py", kind="pins") for n in range(44)]
    text = render_node(_view(imported_by=edges))
    assert "pinned by 44 tests" in text
    block = text[text.index("pinned by"):].split("\n\n")[0]
    assert len(block.splitlines()) <= 8, "the roster must not become the answer"
    assert "run the suite" in block


def test_the_files_OWN_package_leads_the_dependants() -> None:
    """`fastapi/routing.py` listed twelve `docs_src/` tutorials before the four
    `fastapi/` modules that actually build on it. Both are real importers; only
    one answers "what in this library breaks"."""
    edges = [NodeEdge(file="docs_src/tutorial001.py", kind="import"),
             NodeEdge(file="docs_src/tutorial002.py", kind="import"),
             NodeEdge(file="fastapi/applications.py", kind="import")]
    text = render_node(_view(file="fastapi/routing.py", imported_by=edges))
    body = text[text.index("imported by"):]
    assert body.index("fastapi/applications.py") < body.index("docs_src/tutorial001.py")
