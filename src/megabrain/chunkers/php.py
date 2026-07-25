"""PHP — the shared tree-sitter walk, bound to its language table.

The grammar is an optional extra: without it installed, parsing REPORTS failure
and the file still lands in the index as line windows. A missing package is not
a reason for a repository to become unsearchable.
"""

from __future__ import annotations

from ._specs import PHP_SPEC
from .treesitter import parse_with
from .units import Parsed

__all__ = ["parse"]


def parse(relpath: str, source: str) -> Parsed:
    return parse_with(PHP_SPEC, relpath, source)
