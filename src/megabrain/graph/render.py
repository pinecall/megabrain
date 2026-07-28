"""A node view as text — the edges and the outline, never the code.

Same rule `grep` is built on: the caller's editor opens the file anyway, so a
body pasted here is billed twice. What this sells is the half a `Read` cannot
supply — who depends on this file, which cluster it lives in, and which files
do the same job without ever importing it.
"""

from __future__ import annotations

from ..contracts import NodeEdge, NodeView

__all__ = ["render_node", "MAX_LISTED"]

MAX_LISTED = 40
"""Rows per section. A god file has hundreds of dependants and the tail of that
list answers nothing the head did not — the count above it stays exact."""


def render_node(view: NodeView) -> str:
    """`## path` + cluster, both edge directions by kind, twins, the outline."""
    cluster = view["community_label"] or f"cluster {view['community']}"
    lines = [f"# {view['file']}  ({cluster} · degree {view['degree']})"]
    if view["resolved_from"] != view["file"]:
        lines.append(f"resolved from: {view['resolved_from']}")
    lines += [
        *_edges("imports", "→", _per_file(view["imports"])),
        # The half a reader cannot get by opening the file: what needs this is
        # invisible from inside it, and it is what decides whether a change is
        # safe.
        *_edges("imported by", "←", _per_file(view["imported_by"])),
        *_edges("semantic twins (no edge between them)", "≈",
                [f"{tie['file']}  {tie['score']:.2f}" for tie in view["semantic"]]),
        *_symbols(view),
    ]
    return "\n".join(lines)


def _per_file(edges: list[NodeEdge]) -> list[str]:
    """One row per FILE, its kinds joined — the same rule the map's links use.

    A file that both imports and calls this one is ONE dependant. Listed twice
    it reads as two, and the count above the list is exactly what a caller
    reads to decide whether a change is contained: "imported by (8)" for four
    files argues against acting on a fact that is not true.
    """
    kinds: dict[str, list[str]] = {}
    for edge in edges:
        kinds.setdefault(edge["file"], []).append(edge["kind"])
    return [f"{path}  [{'/'.join(sorted(set(found)))}]"
            for path, found in sorted(kinds.items())]


def _edges(title: str, arrow: str, rows: list[str]) -> list[str]:
    if not rows:
        return [f"\n{title}: none"]
    shown = rows[:MAX_LISTED]
    tail = ([f"  … {len(rows) - MAX_LISTED} more"]
            if len(rows) > MAX_LISTED else [])
    return [f"\n{title} ({len(rows)}):", *(f"  {arrow} {row}" for row in shown),
            *tail]


def _symbols(view: NodeView) -> list[str]:
    """The outline with REAL line ranges — what turns an open into a jump."""
    symbols = view["symbols"]
    if not symbols:
        return ["\ndeclares: nothing the index could name"]
    shown = symbols[:MAX_LISTED]
    tail = ([f"  … {len(symbols) - MAX_LISTED} more"]
            if len(symbols) > MAX_LISTED else [])
    return [f"\ndeclares ({len(symbols)}):",
            *(f"  L{s['line']}-{s['end_line']}  {s['kind']} {s['name']}"
              for s in shown), *tail]
