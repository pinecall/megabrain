"""The merge half of split-then-merge: fold small neighbours together.

A one-line helper embedded alone is a vector with almost no signal, and it
crowds a result list with an entry nobody wanted. Adjacent small definitions
are usually one idea, so they become one chunk — up to the budget, never past.
"""

from __future__ import annotations

from typing import Sequence

from ._spans import Cost, Span

__all__ = ["merge"]


def merge(spans: Sequence[Span], cost: Cost, budget: int) -> list[Span]:
    """Fold consecutive spans while the result stays inside `budget`.

    A span already at or over budget is never merged into: it has just been
    split, and growing it again would undo that.
    """
    out: list[Span] = []
    for span in spans:
        if out and _fits(out[-1], span, cost, budget):
            out[-1] = _join(out[-1], span)
        else:
            out.append(span)
    return out


def _fits(left: Span, right: Span, cost: Cost, budget: int) -> bool:
    if left.part or right.part:
        return False                    # fragments of a split unit stay apart
    if cost(left) >= budget or cost(right) >= budget:
        return False
    return cost(left) + cost(right) <= budget


def _join(left: Span, right: Span) -> Span:
    """The merged span names EVERYTHING it holds.

    Keeping only the first name would make the other definitions invisible in a
    result list: the chunk contains them, so a reader scanning names would
    conclude the search had missed them.
    """
    names = [n for n in (left.name, right.name) if n]
    kind = left.kind if left.kind == right.kind else "block"
    return Span(left.start, right.end, kind, ", ".join(names) or None)
