"""One file's entry, CORE or RELATED.

Apart from the page assembly because they answer a different question: `render`
decides what the whole answer looks like, these decide what ONE file gets to say
for itself — its matched span, what else it declares, and where to look next.
"""

from __future__ import annotations

from ...contracts import Tier1File, Tier2File
from ._fence import fenced

__all__ = ["rest_of_file", "related_entry"]

REST_OF_FILE_SYMBOLS = 20
RELATED_SYMBOLS = 6


def rest_of_file(file: Tier1File, covered: list[tuple[int, int]]) -> list[str]:
    """What the file declares OUTSIDE the matched spans.

    The reader is being handed a file; the parts that did not match are how
    they judge whether it is the right one, at one line each.
    """
    rest = [s for s in file["symbols"]
            if not any(lo <= s["line"] <= hi for lo, hi in covered)]
    if not rest:
        return []
    return ["\nrest of file:",
            *(f'- `{s["signature"]}` L{s["line"]}' + (f' — {s["doc"]}' if s["doc"] else "")
              for s in rest[:REST_OF_FILE_SYMBOLS])]


def related_entry(file: Tier2File, *, compact: bool, related_code: bool) -> list[str]:
    """One RELATED file as a map entry: why it is here, and where to look."""
    via = " ·via-graph" if file["via_graph"] else ""
    matched = f' · matched: {", ".join(file["matched"])}' if file["matched"] else ""
    doc = f' — {file["doc"]}' if file["doc"] else ""
    out = [f'### {file["file"]}  `{file["score"]:.2f}`{via}{matched}{doc}']
    best = file["best_chunk"]
    if best and not compact:
        out.append(f'**{best["name"] or best["kind"]}** '
                   f'L{best["start_line"]}-{best["end_line"]}')
        if related_code:
            out += fenced(best["text"], file["file"])
    out += [f'- `{s["signature"]}` L{s["line"]}-{s["end_line"]}'
            for s in file["symbols"][:RELATED_SYMBOLS]]
    out.append("")
    return out
