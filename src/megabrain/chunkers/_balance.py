"""Cutting a run of lines into pieces of roughly equal WEIGHT.

Used when a unit is too large to embed and the language offers no seam inside
it, so the only remaining question is where to put the scissors.
"""

from __future__ import annotations

__all__ = ["balance"]


def balance(first_line: int, weights: list[int], budget: int) -> list[tuple[int, int]]:
    """Line ranges whose weights are as even as the budget allows.

    Balanced rather than greedy. Filling each piece to the brim leaves a tiny
    remainder as its own chunk, which is exactly the no-signal fragment the
    merge pass exists to avoid — reintroduced at the end of every long
    function.

    A line heavier than the budget on its own gets a range to itself. It cannot
    be cut further: chunks are a partition of LINES, and splitting mid-line
    would break the invariant that matters more. It is emitted whole rather
    than dragging its neighbours over the limit with it.
    """
    total = sum(weights)
    target = max(1, total // max(2, -(-total // budget)))
    out: list[tuple[int, int]] = []
    start, running = first_line, 0
    for offset, weight in enumerate(weights):
        line = first_line + offset
        if running and (running + weight > budget or running >= target):
            out.append((start, line - 1))
            start, running = line, 0
        running += weight
    out.append((start, first_line + len(weights) - 1))
    return out
