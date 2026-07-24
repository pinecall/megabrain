"""The split half of split-then-merge: cut what is too large to embed.

An oversized chunk averages several unrelated ideas into one vector, which then
matches everything weakly and nothing well. Two strategies, structural first:
cut where the language already has a seam, and fall back to counting lines only
when it has none.
"""

from __future__ import annotations

from ._balance import balance
from ._spans import Cost, Span
from .units import Unit

__all__ = ["split"]


def split(span: Span, cost: Cost, budget: int) -> list[Span]:
    """`span` broken into pieces that each fit, or itself when it already does."""
    if cost(span) <= budget:
        return [span]
    if span.children:
        return _by_children(span, cost, budget)
    return _by_size(span, cost, budget)


def _by_children(span: Span, cost: Cost, budget: int) -> list[Span]:
    """A container splits at its members, keeping the leading region as a header.

    The header — decorators, docstring, fields — is a retrievable unit in its
    own right: a question about a class's SHAPE should not have to return its
    longest method in order to be answered.
    """
    out: list[Span] = []
    cursor = span.start
    for child in sorted(span.children, key=lambda c: c.start_line):
        if child.start_line > cursor:
            out.extend(_leftover(span, cursor, child.start_line - 1, cost, budget))
        out.extend(split(_member(span, child), cost, budget))
        cursor = child.end_line + 1
    if cursor <= span.end:
        out.extend(_leftover(span, cursor, span.end, cost, budget))
    return out


def _leftover(span: Span, start: int, end: int, cost: Cost, budget: int) -> list[Span]:
    """The region between members — and it goes back through the splitter.

    Emitting it directly is the obvious mistake: a leftover is not small by
    construction. A class whose first method sits 500 lines down (a long
    docstring, a wall of constants, a generated table) produces a header
    larger than everything it precedes, and it would escape the budget the
    splitter exists to enforce.
    """
    return split(Span(start, end, f"{span.kind}_header", span.name), cost, budget)


def _member(parent: Span, child: Unit) -> Span:
    """A member qualified by its container: `Service.handle`, not `handle`."""
    name = f"{parent.name}.{child.name}" if parent.name and child.name else child.name
    return Span(child.start_line, child.end_line, child.kind, name, child.children)


def _by_size(span: Span, cost: Cost, budget: int) -> list[Span]:
    """No inner seam, so cut by WEIGHT.

    Not by line count: lines are not equal. One generated table, one minified
    import, one long string literal — a single line can outweigh a hundred
    around it, and an equal-line split hands all of that weight to one piece,
    which is then over budget while its siblings are nearly empty.

    Balanced rather than greedy: filling each piece to the brim leaves a tiny
    remainder as its own chunk, which is the no-signal fragment the merge pass
    exists to avoid — reintroduced at the end of every long function.

    Parts are marked `"?"` and numbered once the recursion finishes: how many
    there will be is not known yet, and `1/?` tells a reader nothing.
    """
    weights = [cost(Span(n, n, span.kind, span.name))
               for n in range(span.start, span.end + 1)]
    return [Span(start, end, span.kind, span.name, part="?")
            for start, end in balance(span.start, weights, budget)]
