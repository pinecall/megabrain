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
    return _fold(out, first_line, weights, budget)


def _fold(pieces: list[tuple[int, int]], first_line: int, weights: list[int],
          budget: int) -> list[tuple[int, int]]:
    """Merge any adjacent pieces that still fit together.

    The eager cut above overshoots `target` by up to one line per piece; the
    accumulated overshoot leaves a sub-target remainder as its own part — and
    the merge pass is forbidden from touching parts, so without this the
    no-signal fragment both docstrings promise to avoid ships anyway (a real
    corpus produced a part whose entire text was one closing parenthesis).

    This restates merge's guarantee for the one region merge is banned from:
    no adjacent pair of emitted pieces may be foldable within the budget.
    Total weight exceeds the budget here by construction — balance is only
    called for oversized spans — so folding can never collapse to one piece
    covering the whole span.
    """
    def weight_of(piece: tuple[int, int]) -> int:
        start, end = piece
        return sum(weights[start - first_line:end - first_line + 1])

    folded = list(pieces)
    changed = True
    while changed:
        changed = False
        for i in range(len(folded) - 1):
            if weight_of(folded[i]) + weight_of(folded[i + 1]) <= budget:
                folded[i:i + 2] = [(folded[i][0], folded[i + 1][1])]
                changed = True
                break
    return folded
