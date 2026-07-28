"""Naming HOW the built-in chunks a file poorly: table, blob, or window.

Liberal by design — the ab_gate is the real arbiter, so a diagnosis only has
to be plausible, never certain.
"""

from __future__ import annotations

import ast

from ..indexing.chunking import chunker_for
from ..indexing.strategies import Strategy

__all__ = ["diagnose", "SHAPE_RANK", "BUDGET", "MIN_LINES"]

BUDGET = 4000
BLOB_FRAC = 0.55           # largest chunk this share of a file\'s chars = a blob
MIN_LINES = 120            # only large files are worth specializing

# Confidence by shape: a data table is the proven case; a blob or line-window
# fallback is plausible but weaker. The target picks the strongest so the gate
# measures where specialization is most likely to win.
SHAPE_RANK = {"table": 3, "blob": 2, "window": 1}


def diagnose(relpath: str, source: str,
              strategy: Strategy) -> tuple[str, str] | None:
    if len(source.splitlines()) < MIN_LINES:
        return None
    try:
        result = chunker_for(strategy).chunk_file(relpath, source)
    except Exception:                                   # noqa: BLE001
        return None
    if not result.chunks:
        return None
    total_nws = sum(c.nws_chars for c in result.chunks) or 1
    biggest = max(c.nws_chars for c in result.chunks)
    if relpath.endswith(".py") and (table := _dominant_collection(source)):
        return "table", (f"a {table[0]}-entry dict/list literal spans "
                         f"~{int(table[1] * 100)}% of the file; the built-in "
                         f"leaves it in {len(result.chunks)} coarse chunk(s), so "
                         f"a query about one entry retrieves a whole blob")
    if biggest > BLOB_FRAC * total_nws:
        return "blob", (f"the built-in puts ~{int(100 * biggest / total_nws)}% of "
                        f"this {result.total_lines}-line file in one chunk")
    windows = [c for c in result.chunks
               if c.part or (c.kind in ("file", "module") and c.nws_chars > BUDGET)]
    if windows:
        return "window", (f"the built-in falls back to {len(windows)} arbitrary "
                          f"line-window chunk(s)")
    return None


def _dominant_collection(source: str) -> tuple[int, float] | None:
    """The biggest dict/list literal, when it dominates the file."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    best, entries = 0, 0
    total = max(1, len(source.splitlines()))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict | ast.List):
            continue
        elements = node.keys if isinstance(node, ast.Dict) else node.elts
        if len(elements) <= 10:
            continue
        span = (node.end_lineno or node.lineno) - node.lineno
        if span > best:
            best, entries = span, len(elements)
    return (entries, round(best / total, 2)) if best > 0.3 * total else None
