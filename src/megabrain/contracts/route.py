"""A route through the graph, and the evidence for each step.

Separate from the map because it is a different kind of object: the map is
DRAWN, a route is READ. Everything here exists so a reader can follow the chain
without opening five files — which means every field is either a fact from the
index or an admission that a fact is missing.
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["CodeSnip", "HopCode", "Hop", "GraphPath"]


class CodeSnip(TypedDict, total=False):
    """A window of REAL indexed code, with the rows worth looking at marked."""

    file: str
    start_line: int
    text: str
    highlight: str           # the symbol this window is about
    hi_rows: list[int]       # window-relative rows: the exact call/def lines
    in_symbol: str | None    # whose body the call sits in — use sites only


class HopCode(TypedDict):
    """The evidence for one hop: where the carrier is used, where it is defined.

    `verified` distinguishes an AST-resolved use from an inferred one, and the
    studio says which — a route presented as certain when it is a guess is
    worse than a route that admits the difference.
    """

    symbol: str
    verified: bool
    use: CodeSnip | None
    definition: CodeSnip | None


class Hop(TypedDict, total=False):
    """One step of a route, and why it exists."""

    file: str
    via: str                 # "import", "call/import", "semantic 0.91", or ""
    symbols: list[str]       # the names that carry this hop, strongest first
    code: HopCode | None


class GraphPath(TypedDict):
    """How two files are connected, if they are.

    `chain` is the honest part: a route can be a call chain (a reaches b
    through c) or a MEETING (a and b both call into c and never into each
    other). Presenting the second as the first invents a flow that does not
    exist, so the meeting point is named instead.
    """

    source: str
    target: str
    hops: list[Hop]          # source … target, empty when unreachable
    found: bool
    flipped: bool            # presented in call-flow order, against the ask
    chain: bool
    meet: str | None         # the file where the two sides actually meet
    meet_kind: str | None    # "callee" (both call in) or "caller" (it calls both)
    ms: int
