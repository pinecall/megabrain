"""The strategies that ship with the engine.

Each one is a few lines: a tuple of extensions and a parser. That is the point
of the Protocol — a language is configuration, not code in the indexer.
"""

from __future__ import annotations

from ..chunkers import Parsed
from ..chunkers import python as python_parser
from .strategies import Registry, Strategy

__all__ = ["PythonStrategy", "default_registry"]


class PythonStrategy:
    exts: tuple[str, ...] = (".py", ".pyi")

    def parse(self, relpath: str, source: str) -> Parsed:
        return python_parser.parse(relpath, source)

    def edges(self, relpath: str, source: str,
              context: object) -> list[tuple[str, str]] | None:
        return None          # the import graph lands with the edges package


def default_registry(extra: list[Strategy] | None = None) -> Registry:
    """The built-ins, with any caller-supplied strategies taking precedence."""
    return Registry([PythonStrategy()], extra=extra or [])
