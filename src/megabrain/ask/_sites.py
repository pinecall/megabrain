"""The edit sites: the model names symbols, the ENGINE numbers them.

`grep` exists because the host's editor makes you open the file anyway, so
citing the code back is work paid for twice — the reason `megabrain_code` was
retired. What a grep replacement owes is narrower and cheaper: which files,
which symbols inside them, one line on why each matters, and the exact range to
jump to.

The split of labour is the design, and both halves were measured. Asking a model
for line numbers is rejected in `prompt.py`: "unnumbered, `[[k:lo-hi]]` citations
landed a few lines off and cut functions mid-body." Asking it which symbol
matters is what it is good at. So the model writes `send_file` and the index
reads L425-448, where it cannot be off by one.
"""

from __future__ import annotations

import re

from ..storage import Store

__all__ = ["sites_from", "MAX_NOTE", "ROW"]

MAX_NOTE = 100
"""Characters of explanation per symbol.

The reader is about to open the file; this line only has to say why THIS symbol
and not its neighbour. Unbounded, it grows back into the walkthrough `ask`
already gives you."""

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

ROW = re.compile(r"^\s*([^|\n]+?\.[A-Za-z0-9]+)\s*\|\s*([^|\n]+?)\s*\|\s*([^\n]*)$",
                 re.MULTILINE)
"""`path | symbol | note`, one per line.

The `\\.[A-Za-z0-9]+` on the path is what separates a data row from prose that
happens to contain a pipe: a path carries a file extension and a sentence does
not. Models preface and summarise no matter what they are told, so the parse
takes rows and ignores everything else rather than failing on the first
paragraph."""


def sites_from(store: Store, raw: str, *, root: str = "") -> str:
    """The model's rows, grouped by file, with real line ranges from the index."""
    del root
    grouped: dict[str, list[str]] = {}
    for path, symbol, note in ROW.findall(raw):
        span = _span(store, path.strip(), symbol.strip())
        if span is None:
            continue
        low, high = span
        grouped.setdefault(path.strip(), []).append(
            f"  L{low}-{high}  {symbol.strip()} — {note.strip()[:MAX_NOTE]}")
    return "".join(f"## {path}\n" + "\n".join(rows) + "\n\n"
                   for path, rows in grouped.items())


def _span(store: Store, path: str, symbol: str) -> tuple[int, int] | None:
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
