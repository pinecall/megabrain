"""A parser that returns the units a test names, so the chunking ENGINE can be
tested without a grammar.

Every language plugs into the same seam: source in, units out. Driving that
seam directly keeps the merge/split tests about the policy rather than about
whichever language happened to be used to express the fixture.
"""

from __future__ import annotations

from megabrain.chunkers import Parsed, Unit

UnitSpec = tuple[int, int, str, str]      # (start, end, kind, name)


def source_of(lines: int) -> str:
    """A file with distinguishable, non-blank lines."""
    return "".join(f"line {n}\n" for n in range(1, lines + 1))


def parser_for(specs: list[UnitSpec], *, ok: bool = True,
               children: dict[str, list[UnitSpec]] | None = None):
    """A parse function yielding exactly `specs` (with optional nested units).

    `children` maps a unit name to the units inside it — how a class offers its
    methods as cut points when it is too big to keep whole.
    """
    kids = children or {}

    def parse(relpath: str, source: str) -> Parsed:      # noqa: ARG001 — ParseFn shape
        """Ignores the source: the units ARE the fixture. That is what keeps
        the merge/split tests about the policy rather than about whichever
        language happened to be used to write the example."""
        return Parsed(units=tuple(_unit(spec, kids) for spec in specs),
                      symbols=(), skeleton="", ok=ok)

    return parse


def _unit(spec: UnitSpec, kids: dict[str, list[UnitSpec]]) -> Unit:
    start, end, kind, name = spec
    return Unit(start_line=start, end_line=end, kind=kind, name=name,
                children=tuple(_unit(c, kids) for c in kids.get(name, [])))
