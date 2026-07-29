"""A node view as text — the edges and the outline, never the code.

Same rule `grep` is built on: the caller's editor opens the file anyway, so a
body pasted here is billed twice. What this sells is the half a `Read` cannot
supply — who depends on this file, and which files do the same job without
ever importing it.

Every shape here was forced by a real repository. fastapi's `routing.py` had 96
dependants of which FOUR were source, capped by ALPHABET (a repo whose source
sorts after its specs loses the rows that decide whether a change is safe),
under 156 lines of outline the caller's editor supplies. And a Ruby file
another file requires rendered `imported by: none` — dead code, per this tool's
own description — because megabrain reads no Ruby import graph.
"""

from __future__ import annotations

from ..contracts import NodeEdge, NodeView
from ..search.paths import is_demo, is_test
from ..storage import PIN_KIND
from .capability import edges_extracted, no_edges_note
from .outline import outline_of
from .relations import pinned_by, twins_of

__all__ = ["render_node", "MAX_LISTED"]

MAX_LISTED = 40
"""Edge rows per direction. Source first, so what the cap drops is the tail of
the tests — never the dependant a change has to answer to."""

def render_node(view: NodeView) -> str:
    """`# path` + cluster, both edge directions by kind, twins, the outline."""
    cluster = view["community_label"] or f"cluster {view['community']}"
    known = edges_extracted(view["file"])
    home = view["file"].rsplit("/", 1)[0] + "/" if "/" in view["file"] else ""
    lines = [f"# {view['file']}  ({cluster} · degree {view['degree']})"]
    if view["resolved_from"] != view["file"]:
        lines.append(f"resolved from: {view['resolved_from']}")
    # A pin is a test PINNING this file, not code importing it. Counted as a
    # dependant it inflates the number a reader uses to decide whether a change
    # is contained — "what breaks" and "what goes red" are different questions.
    depends = [e for e in view["imported_by"] if e["kind"] != PIN_KIND]
    pinned = {e["file"] for e in view["imported_by"] if e["kind"] == PIN_KIND}
    lines += [
        *_edges("imports", "→", view["imports"], known, home),
        # The half a reader cannot get by opening the file: what needs this is
        # invisible from inside it, and it decides whether a change is safe.
        *_edges("imported by", "←", depends, known, home),
        *pinned_by(pinned - {e["file"] for e in depends}),
        *twins_of(view["semantic"]),
        *outline_of(view["symbols"]),
    ]
    return "\n".join(lines)


def _edges(title: str, arrow: str, edges: list[NodeEdge], known: bool,
           view_home: str = "") -> list[str]:
    """One row per FILE with its kinds joined, SOURCE first.

    A file that both imports and calls this one is ONE dependant; listed twice
    it reads as two. Tests and examples sort last because they are the rows a
    cap may drop without costing the reader an answer, and within the source
    rows the file's OWN package leads: fastapi's `routing.py` listed twelve
    `docs_src/` tutorials above the four modules that build on it, and only
    those four answer "what in this library breaks"."""
    if not edges:
        return [f"\n{title}: {'none' if known else no_edges_note()}"]
    home = view_home
    rows = sorted({e["file"] for e in edges},
                  key=lambda p: (_rank(p), not p.startswith(home), p))
    kinds = {path: sorted({e["kind"] for e in edges if e["file"] == path})
             for path in rows}
    body = [f"  {arrow} {path}  [{'/'.join(kinds[path])}]" for path in rows[:MAX_LISTED]]
    if len(rows) > MAX_LISTED:
        body.append(f"  … {len(rows) - MAX_LISTED} more")
    return [f"\n{title} ({_counted(rows)}):", *body]


def _rank(relpath: str) -> int:
    """Source, then tests, then examples and docs."""
    return 1 if is_test(relpath) else 2 if is_demo(relpath) else 0


def _counted(rows: list[str]) -> str:
    """`96 — 4 source, 92 tests/examples`. The split is the actionable half: a
    file with ninety dependants and four of them real is a contained change,
    and the total alone argues the opposite."""
    aside = sum(1 for path in rows if _rank(path))
    if not aside:
        return str(len(rows))
    return f"{len(rows)} — {len(rows) - aside} source, {aside} tests/examples"

