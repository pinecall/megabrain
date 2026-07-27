"""Turning internal records into the wire contracts.

One place that knows how a `ChunkMeta` becomes a `ChunkHit`, so the shape the
MCP client and the studio see is decided here rather than at four call sites
that can drift apart.

Named for the conversion, not for rendering: `render/` turns these contracts
into text for a human, which is a different job at a different layer, and two
modules called render would be one word covering both.
"""

from __future__ import annotations

from ...contracts import ChunkHit, ChunkRef, SymbolRef
from ...storage.model import ChunkMeta
from ...storage.rows import SymbolRow

__all__ = ["to_ref", "to_hit", "to_outline", "OUTLINE_KINDS"]

# Symbol kinds worth putting in a file outline. Display only — an outline is
# what a reader scans to decide whether to open the file, never an input to
# ranking.
OUTLINE_KINDS = frozenset({
    "class", "function", "async_function", "method", "async_method",
    "constant", "const", "var", "interface", "type", "enum", "module", "heading",
})


def to_ref(meta: ChunkMeta) -> ChunkRef:
    return ChunkRef(id=meta.id, file=meta.file, kind=meta.kind, name=meta.name,
                    part=meta.part, start_line=meta.start_line, end_line=meta.end_line,
                    text=meta.text, breadcrumb=meta.breadcrumb)


def to_hit(meta: ChunkMeta, score: float) -> ChunkHit:
    return ChunkHit(**to_ref(meta), score=score)


def to_outline(symbol: SymbolRow) -> SymbolRef:
    """A storage row -> the wire contract.

    The boundary where an untyped database row becomes a shape the studio and
    the MCP client rely on, so the narrowing is explicit rather than inherited
    from `Any` and quietly spread to every caller.
    """
    return SymbolRef(name=str(symbol["name"]), kind=str(symbol["kind"]),
                     line=int(symbol["line"]), end_line=int(symbol["end_line"]),
                     signature=_text(symbol.get("signature")),
                     doc=_text(symbol.get("doc")))


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None
