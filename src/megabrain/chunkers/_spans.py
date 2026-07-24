"""Turning a language's units into a gapless sequence of line spans.

Two jobs, both about coverage rather than policy: give every line an owner, and
give each owner a name.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Sequence

from .units import Unit

__all__ = ["Span", "Cost", "cover", "renumber"]


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int
    kind: str
    name: str | None
    children: tuple[Unit, ...] = ()
    part: str | None = None          # "2/5" once an oversized span is cut up

    @property
    def lines(self) -> int:
        return self.end - self.start + 1


Cost = Callable[[Span], int]
"""Non-whitespace size of a span — the budget's unit of measure."""


def cover(units: Sequence[Unit], total_lines: int) -> list[Span]:
    """Every line from 1 to `total_lines`, owned by exactly one span.

    The gap BEFORE a unit is attached to it, not emitted separately: comments,
    decorators and blank lines above a definition are about that definition,
    and a docstring banner cut away from its function is noise in both halves.

    Anything after the last unit becomes a trailing span — module-level code at
    the bottom of a file is still code.
    """
    if total_lines <= 0:
        return []
    if not units:
        return [Span(1, total_lines, "file", None)]

    spans: list[Span] = []
    cursor = 1
    for unit in sorted(units, key=lambda u: u.start_line):
        if unit.end_line < cursor:
            continue                     # nested or duplicate: the outer one owns it
        spans.append(Span(cursor, unit.end_line, unit.kind, unit.name, unit.children))
        cursor = unit.end_line + 1
    if cursor <= total_lines:
        spans.append(Span(cursor, total_lines, "module", None))
    return spans


def renumber(spans: Sequence[Span]) -> list[Span]:
    """Stamp `k/n` on consecutive fragments of one split unit.

    Done after all cutting rather than during it, because how many parts there
    are is only known once the recursion finishes — and a part labelled `1/?`
    tells a reader nothing.
    """
    out = list(spans)
    runs: dict[tuple[str | None, str], list[int]] = {}
    for i, span in enumerate(out):
        if span.part == "?":
            runs.setdefault((span.name, span.kind), []).append(i)
    for indexes in runs.values():
        for position, i in enumerate(indexes, start=1):
            out[i] = replace(out[i], part=f"{position}/{len(indexes)}")
    return out
