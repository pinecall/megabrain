"""A small window of real code around a KNOWN line.

Around a known line, never around the first word match: the anchor is the
definition line or an AST-verified call site, so the window cannot land on a
comment, a string, or a same-named local. `hi_rows` are the window-relative
rows to highlight — the exact call lines — because a highlight on the wrong row
teaches the reader something false in the most convincing way available.
"""

from __future__ import annotations

import re
from typing import Sequence

from ...contracts import CodeSnip
from ...storage.model import ChunkMeta

__all__ = ["snip_at", "enclosing_symbol", "SNIP_LINES"]

SNIP_LINES = 22


def snip_at(chunks: Sequence[ChunkMeta], symbol: str, *, at_line: int | None = None,
            at_lines: Sequence[int] = ()) -> CodeSnip | None:
    """The window of indexed text holding `at_line` (or the first of
    `at_lines`), falling back to a word match only when there is no line at
    all — which is the non-Python case, where nothing better exists."""
    anchor = at_line if at_line is not None else (at_lines[0] if at_lines else None)
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    for chunk in chunks:
        lines = chunk.text.splitlines()
        row = _row_in(chunk, lines, anchor, pattern)
        if row is None:
            continue
        low = max(0, row - SNIP_LINES // 3)
        high = min(len(lines), low + SNIP_LINES)
        start = chunk.start_line + low
        marks = [line - start for line in (at_lines or ([anchor] if anchor else []))
                 if start <= line < start + (high - low)]
        return CodeSnip(file=chunk.file, start_line=start,
                        text="\n".join(lines[low:high]), highlight=symbol,
                        hi_rows=sorted(set(marks)))
    return None


def _row_in(chunk: ChunkMeta, lines: list[str], anchor: int | None,
            pattern: re.Pattern[str]) -> int | None:
    if anchor is not None:
        within = chunk.start_line <= anchor <= chunk.end_line
        return anchor - chunk.start_line if within else None
    return next((index for index, line in enumerate(lines) if pattern.search(line)),
                None)


def enclosing_symbol(symbols: Sequence[dict[str, object]], line: int) -> str | None:
    """The innermost def or class containing `line`.

    The story's connective tissue: a call site means nothing without knowing
    whose body it is in. Innermost, so a method wins over its class.
    """
    best: dict[str, object] | None = None
    for entry in symbols:
        start = int(entry["line"] or 0)
        end = int(entry["end_line"] or start)  # type: ignore[arg-type]
        if start <= line <= end and (best is None or start > int(best["line"] or 0)):
            best = entry
    return str(best["name"]).rsplit(".", 1)[-1] if best else None
