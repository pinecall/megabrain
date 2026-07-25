"""The verb `get`: expand a pointer into code.

A bundle's RELATED tier is a map — file, span, symbols — which is the whole
reason it costs a fraction of the tokens. This is how a reader cashes one of
those pointers in.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..contracts import FileView, SymbolRef
from ..retrieval.bundle._convert import to_outline
from ..storage import Store
from ..storage.locate import resolve_root

__all__ = ["get_code"]


def get_code(start: Path | str, relpath: str, *, symbol: str | None = None) -> FileView:
    """One file's indexed text, or the span of one symbol inside it.

    Served from the INDEX, not from disk: these are the exact lines search
    ranked and pointed at. Reading disk instead would quietly answer about
    code the ranking never saw — so the file is compared against disk and the
    difference is reported rather than papered over.
    """
    root = resolve_root(start)
    with Store(root) as store:
        chunks = store.chunks.read_file(relpath)
        if not chunks:
            raise FileNotFoundError(f"{relpath} is not in the index at {root}")
        symbols = [to_outline(s) for s in store.symbols.read_for(relpath)]
        stale = _changed_on_disk(store, root, relpath)
    # Reassembled LINE-wise, never by string concatenation. Chunks partition a
    # file by line and a chunk's text carries no trailing newline, so joining
    # the strings glued each chunk's last line onto the next chunk's first —
    # one line lost per seam, and every line number after it silently wrong.
    lines = [line for chunk in chunks for line in chunk.text.splitlines()]
    first = min(c.start_line for c in chunks)
    span = _span_of(symbols, symbol) if symbol else (first, first + len(lines) - 1)
    return FileView(
        file=relpath, start_line=span[0], end_line=span[1],
        text="\n".join(lines[span[0] - first:span[1] - first + 1]),
        symbols=symbols, symbol=symbol, stale=stale)


def _span_of(symbols: list[SymbolRef], name: str) -> tuple[int, int]:
    """The named symbol's lines. Matches a bare name against a qualified one,
    so `handle` finds `Service.handle` the way go-to-definition does."""
    for entry in symbols:
        declared = entry["name"]
        if declared == name or declared.rsplit(".", 1)[-1] == name:
            return entry["line"], entry["end_line"]
    raise KeyError(f"no symbol named {name!r} in this file")


def _changed_on_disk(store: Store, root: Path, relpath: str) -> bool:
    """Compared by CONTENT hash, the same way indexing decides what to redo —
    a timestamp moves on every checkout and would cry stale constantly."""
    try:
        source = (root / relpath).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True                # gone from disk is the loudest kind of stale
    return store.files.sha(relpath) != hashlib.sha256(source.encode("utf-8")).hexdigest()
