"""Rendering one spliced block: the header, the fence, the verbatim lines.

Apart from the splice because the two answer different questions — WHICH lines
to show, and what they look like once shown. The header format in particular is
read by two other modules (`_broken`, and the flow cache's chrome stripper), so
the shape it is written in is a contract.
"""

from __future__ import annotations

from ...search.render import lang_of
from ...storage.model import ChunkMeta

__all__ = ["fenced_block"]


def fenced_block(chunk: ChunkMeta, low: int, high: int,
                 seen: set[tuple[int, int, str]]) -> str:
    key = (low, high, chunk.file)
    if key in seen:
        # Models cite their own evidence again when they summarise, and the
        # reader scrolls the same forty lines a second time.
        return ""
    seen.add(key)
    body = _lines(chunk, low, high)
    if not body:
        return ""
    return (f"\n**`{chunk.file}` L{low}-{high}**\n"
            f"```{lang_of(chunk.file)}\n{body}\n```\n")


def _lines(chunk: ChunkMeta, low: int, high: int) -> str:
    """The requested lines of the chunk's own text, verbatim."""
    text = (chunk.text or "").split("\n")
    start = max(0, low - chunk.start_line)
    return "\n".join(text[start:start + (high - low + 1)]).rstrip()
