"""The optional languages, and how the registry is assembled.

Split from the strategies themselves because this is the part with a policy in
it: which languages ship on by default, what happens to the ones whose grammar
is not installed, and which of them carry an import graph.

An edge lane is DATA here — a row gains two functions and the language has a
graph. That is the promise `strategies.py` makes ("adding a language is one
entry in a registry, never a branch in the indexer") applied to the second
half: v2 grew Ruby, Go and PHP graphs by subclassing three times, and v3 had
dropped all three in the rewrite.
"""

from __future__ import annotations

import importlib.util
from typing import Callable

from ..chunkers import Parsed
from ..chunkers.languages import c, cpp, csharp, go, java, php, ruby, rust
from ._lane import EdgeLane
from .edges import (
    go_edges,
    go_packages,
    php_classes,
    php_edges,
    ruby_edges,
    ruby_files,
)
from .strategies import Strategy

__all__ = ["GrammarStrategy", "optional_strategies"]

Edges = list[tuple[str, str]]


class GrammarStrategy:
    """A tree-sitter language: chunking always, an import graph when it has one.

    Retrieval works from day one either way — the graph is an annotation lane,
    and a language without one still gets symbols, chunks and the file-skeleton
    signal.
    """

    def __init__(self, exts: tuple[str, ...], parse: Callable[[str, str], Parsed],
                 lane: EdgeLane | None = None) -> None:
        self.exts = exts
        self._parse = parse
        self._lane = lane


    def parse(self, relpath: str, source: str) -> Parsed:
        return self._parse(relpath, source)

    def edge_context(self, sources: dict[str, str]) -> object:
        return self._lane.context(sources) if self._lane else None

    def edges(self, relpath: str, source: str,
              context: object) -> Edges | None:
        return self._lane.edges(relpath, source, context) if self._lane else None


_RUBY = EdgeLane(ruby_files, ruby_edges)      # type: ignore[arg-type]
_GO = EdgeLane(go_packages, go_edges)         # type: ignore[arg-type]
_PHP = EdgeLane(php_classes, php_edges)       # type: ignore[arg-type]

# (extensions, parser, the grammar package it needs, its import graph or None)
_OPTIONAL: list[tuple[tuple[str, ...], Callable[[str, str], Parsed], str,
                      EdgeLane | None]] = [
    ((".rb", ".rake", ".gemspec"), ruby.parse, "tree_sitter_ruby", _RUBY),
    ((".go",), go.parse, "tree_sitter_go", _GO),
    ((".php",), php.parse, "tree_sitter_php", _PHP),
    ((".rs",), rust.parse, "tree_sitter_rust", None),
    # `.h` goes to C rather than C++: a header is far more often C, and the C
    # grammar reads the declarations either way — where they differ, C++ in a
    # `.h` degrades to declarations, not to nothing.
    ((".c", ".h"), c.parse, "tree_sitter_c", None),
    ((".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"), cpp.parse, "tree_sitter_cpp", None),
    ((".java",), java.parse, "tree_sitter_java", None),
    ((".cs",), csharp.parse, "tree_sitter_c_sharp", None)]


def optional_strategies() -> list[Strategy]:
    """The languages whose grammar is actually installed.

    Gated rather than required: the grammars are wheels with native code, and
    making every install carry four of them to index a Python repository is a
    cost paid by everyone for the benefit of a few. `pip install
    megabrain[languages]` turns them on with no code change.
    """
    return [GrammarStrategy(exts, parse, lane)
            for exts, parse, module, lane in _OPTIONAL
            if importlib.util.find_spec(module) is not None]
