"""C# — the shared tree-sitter walk, bound to its language table."""

from __future__ import annotations

from .._specs_c import CSHARP_SPEC
from ..treesitter import parse_with
from ..units import Parsed

__all__ = ["parse"]


def parse(relpath: str, source: str) -> Parsed:
    return parse_with(CSHARP_SPEC, relpath, source)
