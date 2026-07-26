"""C++ — the shared tree-sitter walk, bound to its language table."""

from __future__ import annotations

from ..treesitter.chunker import parse_with
from ..treesitter.specs.c_family import CPP_SPEC
from ..units import Parsed

__all__ = ["parse"]


def parse(relpath: str, source: str) -> Parsed:
    return parse_with(CPP_SPEC, relpath, source)
