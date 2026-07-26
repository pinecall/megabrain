"""A symbol name, as the line range the reader can jump to.

The engine's half of `grep`'s division of labour: the model names the symbol
because that is what it is good at, and the range comes from the index because
asking a model for line numbers was already measured and rejected — unnumbered,
its ranges "landed a few lines off and cut functions mid-body".
"""

from __future__ import annotations

import re

from ..storage import Store

__all__ = ["span_of", "MAX_SPAN"]

MAX_SPAN = 400
"""Lines a symbol may span and still be an EDIT SITE.

MEASURED on sinatra: asked where to add a helper's tests, the model named
`HelpersTest` and the index dutifully numbered it L5-2109 — a 2 100-line class,
which as a place to jump to is no better than the filename. A site is a method
or a test, and past this the row is a file reference wearing a line range."""

_SEPARATORS = re.compile(r"[.#:]+")
"""Ruby writes `Klass#method`, Python `Klass.method`, C++ `Klass::method`.

MEASURED: the model answered `Sinatra::Helpers#send_file` for a symbol the index
stores as `Sinatra.Helpers.send_file`, and splitting on `.` alone left
`Helpers#send_file`, which matched nothing. The model is reading SOURCE, so it
spells names the way that language does."""

def span_of(store: Store, path: str, symbol: str) -> tuple[int, int] | None:
    """`Class.method` or a bare name, in THIS file, as its real line range.

    Matched on the last segment so the model may write `send_file` for a symbol
    the index stores as `App.send_file` — it is reading source, not the table.
    None when the index cannot number it: a range invented for a symbol nobody
    declared is worse than its absence, because the reader jumps to it.
    """
    wanted = _SEPARATORS.split(symbol.strip("`() "))
    sized = [(_SEPARATORS.split(str(e.get("name", ""))), e)
             for e in store.symbols.read_for(path) if _numbered(e)]
    # QUALIFIED first, and it is not a nicety: asked for `Choice.get_metavar`,
    # matching the last segment alone returned `ParamType.get_metavar` — the base
    # class, 257 lines earlier, because it comes first in the file. A reader sent
    # there reads the wrong override and finds nothing to change.
    for depth in (min(len(wanted), 2), 1):
        tail = wanted[-depth:]
        for parts, entry in sized:
            if parts[-depth:] == tail:
                return int(entry["line"]), int(entry["end_line"])
    return None


def _numbered(entry: dict[str, object]) -> bool:
    """A symbol the index can turn into a jumpable range."""
    low, high = entry.get("line"), entry.get("end_line")
    return (isinstance(low, int) and isinstance(high, int)
            and high - low < MAX_SPAN)
