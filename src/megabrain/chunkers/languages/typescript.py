"""TypeScript, TSX, JavaScript and JSX.

One grammar for all four: the TypeScript grammar is a superset of JavaScript,
and the TSX variant handles the JSX syntax the plain one rejects. Nothing here
but the binding — the walk is `treesitter`, the language is `_specs.TS_SPEC`.
"""

from __future__ import annotations

from .._specs import TS_SPEC
from ..treesitter import parse_with
from ..units import Parsed

__all__ = ["parse"]


def parse(relpath: str, source: str) -> Parsed:
    return parse_with(TS_SPEC, relpath, source)
