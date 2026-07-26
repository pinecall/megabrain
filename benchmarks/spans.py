"""Reading a range out of a file, and pricing it.

Both tools are charged the same way: the tokens of the lines you would actually
put in a context window. Overlapping ranges are merged first, because reading
`Option.__init__` and a window around a hit inside it is one read, not two —
counting them twice would flatter whichever tool returns more overlap.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["tokens", "read_cost", "file_lines", "CHARS_PER_TOKEN"]

CHARS_PER_TOKEN = 4
"""The usual English/code approximation.

Deliberately not a real tokenizer: the comparison is a RATIO between two sets of
the same source text, and any consistent divisor leaves the ratio intact while a
dependency on a tokenizer would make the benchmark unrunnable without one."""


def tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def file_lines(root: Path, relpath: str) -> list[str]:
    return Path(root, relpath).read_text(
        encoding="utf-8", errors="replace").split("\n")


def read_cost(root: Path, spans: list[tuple[str, int, int]]) -> int:
    """Tokens of exactly these ranges, per file, overlaps merged."""
    by_file: dict[str, list[tuple[int, int]]] = {}
    for relpath, low, high in spans:
        by_file.setdefault(relpath, []).append((low, high))
    total = 0
    for relpath, ranges in by_file.items():
        try:
            source = file_lines(root, relpath)
        except OSError:
            continue
        for low, high in _merged(ranges):
            total += tokens("\n".join(source[max(0, low - 1):high]))
    return total


def _merged(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Touching or overlapping ranges, joined."""
    out: list[list[int]] = []
    for low, high in sorted(ranges):
        if out and low <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], high)
        else:
            out.append([low, high])
    return [(low, high) for low, high in out]
