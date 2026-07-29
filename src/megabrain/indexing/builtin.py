"""The strategies that ship with the engine.

Each one is a few lines: a tuple of extensions and a parser. That is the point
of the Protocol — a language is configuration, not code in the indexer.

Python, TypeScript/JavaScript and Markdown are always on; their grammars are
hard dependencies. The rest are gated on their grammar being importable, so a
default install reads the languages most repositories are written in and
`pip install megabrain[languages]` adds the others without changing a line.
"""

from __future__ import annotations

from ..chunkers import Parsed
from ..chunkers.languages import markdown, typescript
from ..chunkers.languages import python as python_parser
from ._languages import optional_strategies
from .edges import ModuleIndex, TsFiles, module_index, python_edges, ts_edges, ts_files
from .strategies import Registry, Strategy

__all__ = ["PythonStrategy", "TypeScriptStrategy", "DocumentStrategy",
           "default_registry", "builtin_strategy_for"]


class PythonStrategy:
    exts: tuple[str, ...] = (".py", ".pyi")
    extracts_edges = True

    def parse(self, relpath: str, source: str) -> Parsed:
        return python_parser.parse(relpath, source)

    def edge_context(self, sources: dict[str, str]) -> object:
        return module_index(sources)

    def edges(self, relpath: str, source: str,
              context: object) -> list[tuple[str, str]] | None:
        """The narrowing IS the type check: a context built by another strategy
        is not this one's to read, and `isinstance` says so without a cast that
        would only be true by convention."""
        return python_edges(relpath, context) if isinstance(context, ModuleIndex) else None


class TypeScriptStrategy:
    """One grammar for six extensions.

    The TypeScript grammar is a superset of JavaScript, and the parser routes
    `.tsx`/`.jsx` to the TSX variant — JSX is a syntax error to the plain one.
    """

    exts: tuple[str, ...] = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
    extracts_edges = True

    def parse(self, relpath: str, source: str) -> Parsed:
        return typescript.parse(relpath, source)

    def edge_context(self, sources: dict[str, str]) -> object:
        return ts_files(sources)

    def edges(self, relpath: str, source: str,
              context: object) -> list[tuple[str, str]] | None:
        return ts_edges(relpath, source, context) if isinstance(context, TsFiles) else None


class DocumentStrategy:
    """Markdown. No edges: a document has no imports, and returning an empty
    list would claim it was examined and found to have none."""

    exts: tuple[str, ...] = (".md", ".markdown", ".mdx")
    extracts_edges = False

    def parse(self, relpath: str, source: str) -> Parsed:
        return markdown.parse(relpath, source)

    def edge_context(self, sources: dict[str, str]) -> object:
        return None

    def edges(self, relpath: str, source: str,
              context: object) -> list[tuple[str, str]] | None:
        return None



def default_registry(extra: list[Strategy] | None = None) -> Registry:
    """The built-ins, with any caller-supplied strategies taking precedence."""
    builtin: list[Strategy] = [PythonStrategy(), TypeScriptStrategy(),
                               DocumentStrategy(), *optional_strategies()]
    return Registry(builtin, extra=extra or [])


def builtin_strategy_for(ext: str) -> Strategy | None:
    """The SHIPPED strategy claiming `ext` — what forge's gates measure
    against, so a repo-local strategy can never be its own reference."""
    return default_registry().for_path(f"x{ext}")
