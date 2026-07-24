"""The language seam.

A language contributes ONE function — source in, `Parsed` out — and the
chunking engine does everything else: attaching gaps, merging small units,
splitting large ones, building breadcrumbs, guaranteeing the partition.

That is the whole extension contract. Adding a language means writing a parser,
never touching the policy, and the policy is tested against a fake parser so it
never depends on any grammar being installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .model import Symbol

__all__ = ["Unit", "Parsed", "ParseFn"]


@dataclass(frozen=True, slots=True)
class Unit:
    """One syntactic region a language offers as a possible chunk boundary.

    Line-based rather than node-based on purpose: the engine never needs the
    parse tree, so a language can produce units from an AST, a regex sweep, or
    a heading scan without changing anything downstream.
    """

    start_line: int          # 1-based, inclusive
    end_line: int            # 1-based, inclusive
    kind: str                # class | function | method | module | heading | …
    name: str | None
    children: tuple["Unit", ...] = ()
    """Inner units, offered as cut points when this one exceeds the budget.

    A class lists its methods here. Empty means indivisible: an oversized unit
    with no children is split into numbered parts instead.
    """

    @property
    def lines(self) -> int:
        return self.end_line - self.start_line + 1


@dataclass(frozen=True, slots=True)
class Parsed:
    """What a language parser returns.

    `ok=False` is not a failure to handle upstream — it records that the
    grammar could not read the file, and the engine still produces a valid
    partition from line windows. A file that is hard to parse is exactly the
    kind nobody can find by hand either.
    """

    units: tuple[Unit, ...]
    symbols: tuple[Symbol, ...]
    skeleton: str            # signatures and docstrings, embedded as one vector
    ok: bool = True


ParseFn = Callable[[str, str], Parsed]
"""(relpath, source) -> Parsed. The only thing a new language must supply."""
