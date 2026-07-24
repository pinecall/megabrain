"""The strategies that ship with the engine.

Each one is a few lines: a tuple of extensions and a parser. That is the point
of the Protocol — a language is configuration, not code in the indexer.
"""

from __future__ import annotations

from ..chunkers import Parsed
from ..chunkers import python as python_parser
from .edges import ModuleIndex, module_index, python_edges
from .strategies import Registry, Strategy

__all__ = ["PythonStrategy", "default_registry"]


class PythonStrategy:
    exts: tuple[str, ...] = (".py", ".pyi")

    def parse(self, relpath: str, source: str) -> Parsed:
        return python_parser.parse(relpath, source)

    def edge_context(self, sources: dict[str, str]) -> object:
        return module_index(sources)

    def edges(self, relpath: str, source: str,
              context: object) -> list[tuple[str, str]] | None:
        """The narrowing IS the type check: a context built by another
        strategy is not this one's to read, and `isinstance` says so without
        a cast that would only be true by convention."""
        return python_edges(relpath, context) if isinstance(context, ModuleIndex) else None


def default_registry(extra: list[Strategy] | None = None) -> Registry:
    """The built-ins, with any caller-supplied strategies taking precedence."""
    return Registry([PythonStrategy()], extra=extra or [])
