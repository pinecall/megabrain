"""Java — the shared tree-sitter walk, bound to its language table."""

from __future__ import annotations

from .._specs_c import JAVA_SPEC
from ..treesitter import parse_with
from ..units import Parsed

__all__ = ["parse"]


def parse(relpath: str, source: str) -> Parsed:
    return parse_with(JAVA_SPEC, relpath, source)
