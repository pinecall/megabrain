"""The file's own declarations, with real line ranges.

The one part of a node view a plain `Read` of the file already supplies — so
it is capped far below the edge lists rather than at the same number. MEASURED
on fastapi: `routing.py` declares 156 symbols, and printing them all buried
the dependants (which nothing but this index can tell you) under the outline
(which the caller\'s editor gives away for free).
"""

from __future__ import annotations

from ..storage.rows import SymbolRow

__all__ = ["outline_of", "MAX_SYMBOLS"]

MAX_SYMBOLS = 15


def outline_of(symbols: list[SymbolRow]) -> list[str]:
    """`declares (n):` and the first rows, or why there are none.

    The line range is what turns an open into a jump, so the count and the
    spans stay exact even when the list is cut.
    """
    if not symbols:
        return ["\ndeclares: nothing the index could name"]
    tail = ([f"  … {len(symbols) - MAX_SYMBOLS} more — open the file for the rest"]
            if len(symbols) > MAX_SYMBOLS else [])
    return [f"\ndeclares ({len(symbols)}):",
            *(f"  L{s['line']}-{s['end_line']}  {s['kind']} {s['name']}"
              for s in symbols[:MAX_SYMBOLS]), *tail]
