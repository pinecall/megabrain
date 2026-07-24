"""The chunking engine: split-then-merge over whatever units a language offers.

One implementation of the recipe, shared by every language. A parser supplies
units; this decides where the chunks actually fall, and guarantees the
partition regardless of what the parser said.
"""

from __future__ import annotations

from ._breadcrumb import breadcrumb
from ._merge import merge
from ._spans import Cost, Span, cover, renumber
from ._split import split
from .model import DEFAULT_BUDGET, Chunk, FileResult, nws
from .units import ParseFn, Unit

__all__ = ["Chunker"]


def _physical_lines(source: str) -> list[str]:
    """Split on \n ONLY — the physical-line model `ast` counts by.

    `str.splitlines()` also breaks on \f, \v, \x1c-\x1e and U+2028/U+2029.
    A form feed inside a string literal (a legal PEP-8 page separator) then
    makes the two models disagree: chunk line numbers drift one past every ast
    symbol after it, and joining the split lines back with \n rewrites the
    \f to a newline — silent corruption of text that is promised verbatim.
    """
    lines = source.split("\n")
    if lines and lines[-1] == "":
        lines.pop()          # a trailing newline is a terminator, not a line
    return lines


class Chunker:
    """Turns source into a partition of chunks.

    `parse` is the only language-specific piece — see `units.ParseFn`.
    """

    def __init__(self, parse: ParseFn, *, repo: str = "",
                 budget: int = DEFAULT_BUDGET) -> None:
        self._parse = parse
        self.repo = repo
        self.budget = budget

    def chunk_file(self, relpath: str, source: str) -> FileResult:
        lines = _physical_lines(source)
        parsed = self._parse(relpath, source)
        spans = self._layout(parsed.units, len(lines), lines)
        return FileResult(
            file=relpath,
            chunks=[self._chunk(relpath, span, lines) for span in spans],
            symbols=list(parsed.symbols),
            skeleton=parsed.skeleton,
            parse_ok=parsed.ok,
            total_lines=len(lines),
        )

    def _layout(self, units: tuple[Unit, ...], total: int, lines: list[str]) -> list[Span]:
        """Cover, split, then merge — in that order.

        Splitting first is what makes the merge safe: it runs over pieces that
        already fit, so folding two of them can never exceed the budget.
        """
        cost = self._cost(lines)
        spans = cover(units, total)
        pieces = [p for span in spans for p in split(span, cost, self.budget)]
        return renumber(merge(pieces, cost, self.budget))

    def _cost(self, lines: list[str]) -> Cost:
        """Budget in NON-whitespace characters, so deeply indented code is not
        punished for its indentation."""
        return lambda span: nws("\n".join(lines[span.start - 1:span.end]))

    def _chunk(self, relpath: str, span: Span, lines: list[str]) -> Chunk:
        return Chunk(
            file=relpath,
            kind=span.kind,
            name=span.name,
            part=span.part,
            start_line=span.start,
            end_line=span.end,
            text="\n".join(lines[span.start - 1:span.end]),
            breadcrumb=breadcrumb(self.repo, relpath, span.name, span.kind),
        ).finalize()
